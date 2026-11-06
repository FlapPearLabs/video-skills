// Read-only NodeTool 0.8.x MCP adapter. A caller supplies an initialized MCP client.
// No arbitrary code, generation, project writes or paid operations are exposed.
const ID = /^[A-Za-z0-9_-]{1,128}$/;
const TIMELINE_NAMES = ['list_timelines','get_timeline','validate_timeline',
  'create_timeline_version','restore_timeline_version','edit_timeline','render_timeline'];

function unpack(response) {
  if (response?.isError) throw new Error('MCP tool returned an error');
  const blocks = response?.content?.filter(x => x.type === 'text') ?? [];
  if (blocks.length !== 1) throw new Error('Unexpected NodeTool response');
  let body;
  try { body = JSON.parse(blocks[0].text); } catch { throw new Error('Invalid NodeTool JSON'); }
  if (body?.ok !== true || !Object.hasOwn(body, 'result')) throw new Error(`NodeTool action failed: ${body?.error ?? 'invalid envelope'}`);
  if (body.result?.error || body.result?.ok === false) throw new Error(`NodeTool operation failed: ${body.result?.error ?? 'unknown error'}`);
  return body.result;
}

export class NodeToolReadAdapter {
  constructor(client) { if (!client || typeof client.listTools !== 'function' || typeof client.callTool !== 'function') throw new Error('Initialized MCP client required'); this.client=client; }
  async #action(title,code) {
    return unpack(await this.client.callTool({name:'execute_code',arguments:{title,risk:'low',description:'',code}}));
  }
  async discover() {
    const listed=await this.client.listTools();
    const tools=listed?.tools;
    if (!Array.isArray(tools)) throw new Error('Invalid MCP tool list');
    const exec=tools.find(t=>t.name==='execute_code');
    if (!exec?.inputSchema?.properties?.code) throw new Error('NodeTool execute_code schema unavailable');
    const hits=await this.#action('Discover timeline tools','return await nodetool.searchTools("timeline", 50);');
    if (!Array.isArray(hits)) throw new Error('Invalid timeline capability list');
    const found=Object.fromEntries(TIMELINE_NAMES.map(name=>{
      const matches=hits.filter(h=>h.name===name && h.module==='timelines' && typeof h.signature==='string');
      return [name,matches.length===1?matches[0]:null];
    }));
    return {server:this.client.getServerVersion?.() ?? null,execute_code_schema:exec.inputSchema,capabilities:found};
  }
  async getTimeline(id) {
    if (typeof id!=='string'||!ID.test(id)) throw new Error('Invalid timeline ID');
    return this.#action('Read timeline',`import { get_timeline } from "@nodetool-ai/sandbox-nodetool/timelines"; return await get_timeline({timeline_id:${JSON.stringify(id)}});`);
  }
}
