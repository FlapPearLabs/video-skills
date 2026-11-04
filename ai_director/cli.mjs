#!/usr/bin/env node
// CLI for deterministic AI Director M0 admission checks; NEVER calls NodeTool or provider APIs.
import fs from 'node:fs';
import path from 'node:path';
import { capabilityMatrix, prepareOperation, recordOperation, deliveryGate } from './runtime.mjs';

const [action, statePath, inputPath] = process.argv.slice(2);
function read(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function json(x) { process.stdout.write(JSON.stringify(x, null, 2) + '\n'); }
function mutate(file, callback) {
  const lockPath=file+'.ai-director.lock';
  const fd=fs.openSync(lockPath, 'wx', 0o600);
  try {
    const next=callback(read(file));
    const tmp=path.join(path.dirname(file), '.ai-director-'+process.pid+'.tmp');
    try {
      fs.writeFileSync(tmp, JSON.stringify(next, null, 2) + '\n', {encoding:'utf8',flag:'wx',mode:0o600});
      fs.renameSync(tmp, file);
    } finally { if(fs.existsSync(tmp)) fs.unlinkSync(tmp); }
    return next;
  } finally { fs.closeSync(fd); fs.unlinkSync(lockPath); }
}
try {
  if(!statePath || !['capabilities','prepare','record','delivery'].includes(action)) {
    throw new Error('Usage: node ai_director/cli.mjs capabilities|prepare|record|delivery STATE.json [request.json]');
  }
  if(action==='capabilities'){
    const result=capabilityMatrix(read(statePath));
    json(result);if(!result.ready)process.exitCode=2;
  }else if(action==='delivery'){
    if(!inputPath)throw new Error('delivery requires evidence.json');
    const result=deliveryGate(read(statePath),read(inputPath));
    json(result);if(!result.passed)process.exitCode=2;
  }else{
    if(!inputPath)throw new Error(action+' requires request/receipt JSON');
    const input=read(inputPath);
    const next=mutate(statePath,s=>action==='prepare'?prepareOperation(s,input):recordOperation(s,input));
    const op=next.operations.find(o=>o.operation_id===(input.operation_id||next.ai_director.active_operation_id));
    json({ok:true,action,operation_id:input.operation_id,operation_status:op?.status||null,active_operation_id:next.ai_director.active_operation_id,
      reserved:next.budget.reserved,spent:next.budget.spent,generation_calls_used:next.budget.generation_calls_used});
  }
}catch(error){
  process.stderr.write(JSON.stringify({ok:false,error:String(error.message||error)},null,2)+'\n');
  process.exitCode=2;
}
