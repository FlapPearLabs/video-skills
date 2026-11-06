import test from 'node:test';
import assert from 'node:assert/strict';
import { TOOLS, capabilityMatrix, prepareOperation, recordOperation, deliveryGate } from '../runtime.mjs';

function state() {
  return {
    schema_version:'0.1', project_id:'synthetic-project', revision_token:'revision-1',
    operations:[],
    budget:{approved_by:'test-user',user_evidence:'fixture-only',unit:'CNY',limit:10,spent:0,reserved:0,max_generation_calls:2,generation_calls_used:0,allowed_ticket_ids:['S03']},
    ai_director:{timeline_id:'synthetic-timeline',active_operation_id:null,
      tool_manifest:TOOLS.map(name=>({name,status:'observed',evidence:'synthetic-only',schema_ref:'fixture:'+name}))}
  };
}
const req=()=>({
  operation_id:'op-1',ticket_id:'S03',tool:'edit_timeline',timeline_id:'synthetic-timeline',expected_revision:'revision-1',
  payload_sha256:'a'.repeat(64),idempotency_key:'idempotency-1',mode:'edit',snapshot_id:'snapshot-1',
  plan_sha256:'b'.repeat(64),allowed_fields:{S03:['asset_ref']},change_guard_ready:true,may_charge:false
});
const paid=()=>({...req(),operation_id:'op-fee',idempotency_key:'idempotency-fee',tool:'render_timeline',mode:'render',may_charge:true,cost_upper_bound:5,cost_unit:'CNY'});
const proof=()=>Object.fromEntries(['native_timeline_validated','real_render_playable','editable_project_reopened','av_review_passed','claims_policy_checked'].map(k=>[k,{status:'observed',ref:'synthetic:'+k}]));

test('unknown and schema-only tools cannot pass readiness',()=>{
  assert.equal(capabilityMatrix(state()).ready,true);
  const s=state();s.ai_director.tool_manifest[0].status='schema_only';
  assert.equal(capabilityMatrix(s).ready,false);
  assert.ok(capabilityMatrix(s).missing.includes(TOOLS[0]));
});
test('invalid or duplicate tools are rejected',()=>{
  const s=state();s.ai_director.tool_manifest.push({...s.ai_director.tool_manifest[0]});
  assert.throws(()=>capabilityMatrix(s),/duplicate/);
});
test('edit preparation preserves input and acquires writer lock',()=>{
  const s=state();const p=prepareOperation(s,req());
  assert.equal(s.operations.length,0);
  assert.equal(p.operations[0].status,'prepared');
  assert.equal(p.ai_director.active_operation_id,'op-1');
});
test('preparation rejects stale revision, absent snapshot and unverified plan',()=>{
  assert.throws(()=>prepareOperation(state(),{...req(),expected_revision:'old'}),/stale/);
  assert.throws(()=>prepareOperation(state(),{...req(),snapshot_id:null}),/snapshot/);
  assert.throws(()=>prepareOperation(state(),{...req(),change_guard_ready:false}),/change guard/);
});
test('duplicate idempotency never resubmits',()=>{
  const s=state();s.operations.push({operation_id:'old',idempotency_key:'idempotency-1',status:'unknown'});
  assert.throws(()=>prepareOperation(s,req()),/duplicate/);
});
test('critical timeline tools cannot bypass edit/snapshot guard by relabeling mode',()=>{
  assert.throws(()=>prepareOperation(state(),{...req(),mode:'generate'}),/unsafe tool\/mode/);
  assert.throws(()=>prepareOperation(state(),{...req(),tool:'restore_timeline_version',mode:'generate'}),/unsafe tool\/mode/);
});
test('not-observed tool is blocked even if listed',()=>{
  const s=state();s.ai_director.tool_manifest[2].status='schema_only';
  assert.throws(()=>prepareOperation(s,req()),/not observed/);
});
test('paid operation holds reserve and charges attempt',()=>{
  const p=prepareOperation(state(),paid());
  assert.equal(p.budget.reserved,5);
  assert.equal(p.budget.generation_calls_used,1);
});
test('paid operation requires approved ticket, cost unit, and known upper bound',()=>{
  assert.throws(()=>prepareOperation(state(),{...paid(),ticket_id:'S99'}),/not authorized/);
  assert.throws(()=>prepareOperation(state(),{...paid(),cost_unit:'USD'}),/cost approval/);
  assert.throws(()=>prepareOperation(state(),{...paid(),cost_upper_bound:null}),/upper bound/);
});
test('budget limit and call cap are enforced',()=>{
  const s=state();s.budget.limit=3;
  assert.throws(()=>prepareOperation(s,paid()),/budget limit/);
  const c=state();c.budget.generation_calls_used=2;
  assert.throws(()=>prepareOperation(c,paid()),/call cap/);
});
test('negative budget balances and call counts cannot create spending capacity',()=>{
  for (const field of ['limit','spent','reserved']) {
    const s=state(); s.budget[field]=-1;
    assert.throws(()=>prepareOperation(s,paid()),/invalid budget/);
  }
  for (const field of ['max_generation_calls','generation_calls_used']) {
    const s=state(); s.budget[field]=-1;
    assert.throws(()=>prepareOperation(s,paid()),/invalid call count/);
  }
});
test('unknown submission retains lock and budget reservation',()=>{
  const p=prepareOperation(state(),paid());
  const u=recordOperation(p,{operation_id:'op-fee',status:'unknown'});
  assert.equal(u.budget.reserved,5);
  assert.equal(u.ai_director.active_operation_id,'op-fee');
  assert.throws(()=>prepareOperation(u,{...paid(),operation_id:'new',idempotency_key:'new'}),/writer lock/);
});
test('pre-dispatch cancellation can release reservation only with evidence',()=>{
  const p=prepareOperation(state(),paid());
  assert.throws(()=>recordOperation(p,{operation_id:'op-fee',status:'cancelled'}),/only proven/);
  const c=recordOperation(p,{operation_id:'op-fee',status:'cancelled',submission_status:'not_sent',cancellation_evidence:'fixture'});
  assert.equal(c.budget.reserved,0);
  assert.equal(c.budget.generation_calls_used,0);
});
test('terminal operation without settlement retains reserve',()=>{
  const p=prepareOperation(state(),paid());
  const a=recordOperation(p,{operation_id:'op-fee',status:'submitted',receipt_ref:'submitted'});
  const b=recordOperation(a,{operation_id:'op-fee',status:'succeeded',receipt_ref:'complete'});
  assert.equal(b.budget.reserved,5);
  assert.equal(b.operations[0].settlement,'pending');
});
test('settled cost cannot exceed reserved cost',()=>{
  const p=prepareOperation(state(),paid());
  const a=recordOperation(p,{operation_id:'op-fee',status:'submitted',receipt_ref:'submitted'});
  assert.throws(()=>recordOperation(a,{operation_id:'op-fee',status:'succeeded',receipt_ref:'done',settlement_evidence:'invoice',actual_cost:6}),/invalid settled/);
  const b=recordOperation(a,{operation_id:'op-fee',status:'succeeded',receipt_ref:'done',settlement_evidence:'invoice',actual_cost:4});
  assert.equal(b.budget.reserved,0);
  assert.equal(b.budget.spent,4);
});
test('deliverables need actual observed proofs and no unresolved writes',()=>{
  const s=state();
  assert.equal(deliveryGate(s,{timeline_id:'synthetic-timeline',proofs:{}}).passed,false);
  assert.equal(deliveryGate(s,{timeline_id:'synthetic-timeline',proofs:proof()}).passed,true);
  const p=prepareOperation(s,paid());
  assert.equal(deliveryGate(p,{timeline_id:'synthetic-timeline',proofs:proof()}).passed,false);
});
