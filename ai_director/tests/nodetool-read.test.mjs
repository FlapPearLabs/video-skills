import test from 'node:test';
import assert from 'node:assert/strict';
import {NodeToolReadAdapter} from '../nodetool-read.mjs';
const response=x=>({content:[{type:'text',text:JSON.stringify(x)}]});
test('read path refuses code injection and never dispatches it',async()=>{
  let calls=0; const a=new NodeToolReadAdapter({listTools(){},async callTool(){calls++;return response({ok:true,result:{}})}});
  assert.equal(a.action,undefined);
  await assert.rejects(a.getTimeline('x";danger()'),/Invalid timeline ID/);
  assert.equal(calls,0);
});
test('discovery requires real execute_code schema and preserves missing capabilities',async()=>{
  const client={async listTools(){return {tools:[{name:'execute_code',inputSchema:{properties:{code:{type:'string'}}}}]}},async callTool(){return response({ok:true,result:[{name:'get_timeline',module:'timelines',signature:'get_timeline({timeline_id: string})'}]})}};
  const result=await new NodeToolReadAdapter(client).discover();
  assert.ok(result.capabilities.get_timeline);
  assert.equal(result.capabilities.render_timeline,null);
  client.listTools=async()=>({tools:[]});
  await assert.rejects(new NodeToolReadAdapter(client).discover(),/schema unavailable/);
});
test('nested NodeTool errors are not accepted as successful reads',async()=>{
  const a=new NodeToolReadAdapter({listTools(){},async callTool(){return response({ok:true,result:{error:'not found'}})}});
  await assert.rejects(a.getTimeline('abc123'),/not found/);
});
