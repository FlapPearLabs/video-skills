// AI Director M0 orchestration safety gates; NO network calls or NodeTool edits.
// Uses existing Video-Skills STATE.json and observed tool/receipt evidence.
const TOOLS = Object.freeze(["list_timelines","get_timeline","edit_timeline","validate_timeline","create_timeline_version","restore_timeline_version","render_timeline"]);

function ensure(c,m){if(!c)throw new Error(m);}

function clone(x){return JSON.parse(JSON.stringify(x));}

function assertState(s){
  ensure(s&&s.schema_version==="0.1"&&Array.isArray(s.operations)&&s.budget&&s.ai_director,"STATE.json missing schema_version=0.1 / operations / budget / ai_director");
  ensure(typeof s.project_id==="string"&&!!s.project_id.trim(),"project_id missing");
  ensure(typeof s.revision_token==="string"&&!!s.revision_token.trim(),"revision_token missing");
  ensure(typeof s.ai_director.timeline_id==="string"&&!!s.ai_director.timeline_id.trim(),"timeline_id missing");
  ensure(Array.isArray(s.ai_director.tool_manifest),"tool_manifest must be array");
}

function capabilityMatrix(s){
  assertState(s);
  const seen=new Set();
  for(const t of s.ai_director.tool_manifest){ensure(t&&typeof t.name==="string"&&!seen.has(t.name),"invalid or duplicate tool name");seen.add(t.name);}
  const tools=TOOLS.map(name=>{
    const t=s.ai_director.tool_manifest.find(x=>x.name===name);
    const observed=!!(t?.status==="observed"&&typeof t.evidence==="string"&&t.evidence.trim()&&typeof t.schema_ref==="string"&&t.schema_ref.trim());
    return {name,observed,evidence:observed?t.evidence:null};
  });
  return {ready:tools.every(t=>t.observed),missing:tools.filter(t=>!t.observed).map(t=>t.name),tools};
}

function prepareOperation(s,r){
  assertState(s);
  ensure(r&&typeof r==="object","request required");
  for(const k of ["operation_id","ticket_id","tool","timeline_id","expected_revision","payload_sha256","idempotency_key","mode"])ensure(typeof r[k]==="string"&&!!r[k].trim(),"missing "+k);
  ensure(["edit","structure","generate","render"].includes(r.mode),"unsupported mode");
  ensure(!s.ai_director.active_operation_id,"writer lock held: reconcile active/unknown operation");
  ensure(!s.operations.some(x=>x.operation_id===r.operation_id||x.idempotency_key===r.idempotency_key),"duplicate operation: reconcile instead of resubmit");
  ensure(r.timeline_id===s.ai_director.timeline_id&&r.expected_revision===s.revision_token,"stale timeline or revision");
  ensure(/^[0-9a-f]{64}$/i.test(r.payload_sha256),"payload_sha256 must be SHA-256 hex");
  const tool=s.ai_director.tool_manifest.find(t=>t.name===r.tool);
  ensure(tool?.status==="observed"&&tool.evidence&&tool.schema_ref,"MCP tool not observed: "+r.tool);
  const restricted={
    list_timelines:[],get_timeline:[],validate_timeline:[],create_timeline_version:[],restore_timeline_version:[],
    edit_timeline:["edit","structure"],render_timeline:["render"]
  };
  if(Object.prototype.hasOwnProperty.call(restricted,r.tool))
    ensure(restricted[r.tool].includes(r.mode),"unsafe tool/mode combination; use a dedicated native integration path");

  if(["edit","structure"].includes(r.mode)){
    ensure(typeof r.snapshot_id==="string"&&!!r.snapshot_id.trim()&&/^[0-9a-f]{64}$/i.test(r.plan_sha256||""),"existing timeline edits require native snapshot + plan SHA");
    ensure(r.change_guard_ready===true&&r.allowed_fields&&typeof r.allowed_fields==="object"&&!Array.isArray(r.allowed_fields)&&Object.keys(r.allowed_fields).length>0,"change guard and allowed_fields required");
    for(const fields of Object.values(r.allowed_fields))ensure(Array.isArray(fields)&&fields.length>0&&fields.every(x=>typeof x==="string"),"invalid allowed_fields");
  }
  ensure(typeof r.may_charge==="boolean","may_charge must be explicit");
  const b=s.budget;
  let reservation=0;
  if(r.may_charge){
    ensure(b.approved_by&&b.user_evidence&&b.unit&&r.cost_unit===b.unit,"cost approval/unit missing");
    ensure(Array.isArray(b.allowed_ticket_ids)&&b.allowed_ticket_ids.includes(r.ticket_id),"ticket not authorized");
    ensure(Number.isFinite(r.cost_upper_bound)&&r.cost_upper_bound>=0,"known cost upper bound required");
    ensure([b.limit,b.spent,b.reserved].every(Number.isFinite)&&b.spent+b.reserved+r.cost_upper_bound<=b.limit,"budget limit exceeded");
    if(["generate","render"].includes(r.mode))ensure(Number.isInteger(b.max_generation_calls)&&Number.isInteger(b.generation_calls_used)&&b.generation_calls_used<b.max_generation_calls,"call cap exceeded");
    reservation=r.cost_upper_bound;
  }
  const n=clone(s);
  n.ai_director.active_operation_id=r.operation_id;
  n.budget.reserved=(n.budget.reserved||0)+reservation;
  const counts=!!(r.may_charge&&["generate","render"].includes(r.mode));
  if(counts)n.budget.generation_calls_used++;
  n.operations.push({
    operation_id:r.operation_id,ticket_id:r.ticket_id,project_id:s.project_id,tool:r.tool,mode:r.mode,
    timeline_id:r.timeline_id,expected_revision:r.expected_revision,payload_sha256:r.payload_sha256,idempotency_key:r.idempotency_key,
    status:"prepared",may_charge:r.may_charge,cost_upper_bound:reservation,cost_unit:r.may_charge?r.cost_unit:null,
    counts_as_attempt:counts,task_id:null,receipt_ref:null,
    change_impact:["edit","structure"].includes(r.mode)?{before_timeline_version:r.snapshot_id,plan_sha256:r.plan_sha256,allowed_fields:r.allowed_fields}:null
  });
  return n;
}

function recordOperation(s,e){
  assertState(s);
  ensure(e&&e.operation_id&&["submitted","running","succeeded","failed","unknown","cancelled"].includes(e.status),"invalid receipt");
  const n=clone(s);
  const op=n.operations.find(x=>x.operation_id===e.operation_id);
  ensure(op&&n.ai_director.active_operation_id===e.operation_id,"receipt does not match active operation");
  const transitions={prepared:["submitted","unknown","cancelled"],submitted:["running","succeeded","failed","unknown"],running:["succeeded","failed","unknown"],unknown:["running","succeeded","failed"]};
  ensure(transitions[op.status]?.includes(e.status),"invalid status transition");
  if(!["unknown","cancelled"].includes(e.status))ensure(typeof e.receipt_ref==="string"&&!!e.receipt_ref,"real receipt_ref required");
  if(e.status==="cancelled")ensure(op.status==="prepared"&&e.submission_status==="not_sent"&&e.cancellation_evidence,"only proven pre-dispatch cancellation releases reservation");
  if(["succeeded","failed"].includes(e.status)&&op.may_charge&&e.settlement_evidence)ensure(Number.isFinite(e.actual_cost)&&e.actual_cost>=0&&e.actual_cost<=op.cost_upper_bound,"invalid settled cost; manual reconciliation required");
  op.status=e.status;op.receipt_ref=e.receipt_ref||op.receipt_ref;op.task_id=e.task_id||op.task_id;
  if(e.status==="cancelled"){
    n.budget.reserved-=op.cost_upper_bound;
    if(op.counts_as_attempt)n.budget.generation_calls_used--;
    op.counts_as_attempt=false;op.submission_status="not_sent";op.cancellation_evidence=e.cancellation_evidence;
    n.ai_director.active_operation_id=null;
  }else if(["succeeded","failed"].includes(e.status)){
    if(op.may_charge){
      if(e.settlement_evidence){
        n.budget.reserved-=op.cost_upper_bound;n.budget.spent+=e.actual_cost;
        op.actual_cost=e.actual_cost;op.settlement_evidence=e.settlement_evidence;op.settlement="settled";
      }else op.settlement="pending";
    }
    n.ai_director.active_operation_id=null;
  }
  return n;
}

function deliveryGate(s,e){
  assertState(s);
  const problems=[];
  if(s.ai_director.active_operation_id)problems.push("writer lock not released");
  if(s.operations.some(x=>x.status==="unknown"))problems.push("unknown operation");
  if(!e||e.timeline_id!==s.ai_director.timeline_id)problems.push("timeline readback identity missing");
  const required=["native_timeline_validated","real_render_playable","editable_project_reopened","av_review_passed","claims_policy_checked"];
  for(const k of required){
    const proof=e?.proofs?.[k];
    if(!(proof?.status==="observed"&&typeof proof.ref==="string"&&proof.ref.trim()))problems.push("missing observed proof: "+k);
  }
  return {passed:problems.length===0,production_complete:problems.length===0,problems};
}

export { TOOLS, assertState, capabilityMatrix, prepareOperation, recordOperation, deliveryGate };
