import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const CLI=fileURLToPath(new URL('../cli.mjs',import.meta.url));
const toolNames=['list_timelines','get_timeline','edit_timeline','validate_timeline','create_timeline_version','restore_timeline_version','render_timeline'];
function fixtures(){
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'ai-director-test-'));
  const state=path.join(dir,'STATE.json');
  fs.writeFileSync(state,JSON.stringify({
    schema_version:'0.1',project_id:'synthetic',revision_token:'v1',operations:[],
    budget:{approved_by:'test',user_evidence:'fixture',unit:'CNY',limit:10,spent:0,reserved:0,max_generation_calls:2,generation_calls_used:0,allowed_ticket_ids:['S03']},
    ai_director:{timeline_id:'t1',active_operation_id:null,tool_manifest:toolNames.map(name=>({name,status:'observed',evidence:'synthetic',schema_ref:'fixture'}))}
  }));
  return {dir,state};
}
function run(...args){return spawnSync(process.execPath,[CLI,...args],{encoding:'utf8'});}
test('CLI capabilities works offline with synthetic fixture',()=>{
  const f=fixtures();
  try{const x=run('capabilities',f.state);assert.equal(x.status,0);assert.equal(JSON.parse(x.stdout).ready,true);}
  finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});
test('CLI prepare and record persist state without MCP calls',()=>{
  const f=fixtures();
  try{
    const op=path.join(f.dir,'op.json');
    fs.writeFileSync(op,JSON.stringify({
      operation_id:'op1',ticket_id:'S03',tool:'edit_timeline',timeline_id:'t1',expected_revision:'v1',payload_sha256:'a'.repeat(64),
      idempotency_key:'i1',mode:'edit',snapshot_id:'synthetic-snapshot',plan_sha256:'b'.repeat(64),
      allowed_fields:{S03:['asset_ref']},change_guard_ready:true,may_charge:false
    }));
    const a=run('prepare',f.state,op);assert.equal(a.status,0,a.stderr);
    assert.equal(JSON.parse(fs.readFileSync(f.state)).ai_director.active_operation_id,'op1');
    assert.equal(run('prepare',f.state,op).status,2);
    const rec=path.join(f.dir,'receipt.json');
    fs.writeFileSync(rec,JSON.stringify({operation_id:'op1',status:'submitted',receipt_ref:'synthetic-receipt'}));
    assert.equal(run('record',f.state,rec).status,0);
    assert.equal(JSON.parse(fs.readFileSync(f.state)).operations[0].status,'submitted');
    assert.equal(fs.existsSync(f.state+'.ai-director.lock'),false);
  }finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});
test('CLI delivery rejects incomplete evidence',()=>{
  const f=fixtures();
  try{
    const evidence=path.join(f.dir,'evidence.json');fs.writeFileSync(evidence,JSON.stringify({timeline_id:'t1',proofs:{}}));
    const x=run('delivery',f.state,evidence);assert.equal(x.status,2);assert.equal(JSON.parse(x.stdout).passed,false);
  }finally{fs.rmSync(f.dir,{recursive:true,force:true});}
});
