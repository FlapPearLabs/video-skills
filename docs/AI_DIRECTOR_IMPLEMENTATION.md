# AI Director · 实现与联调指南 v0.2

## 已有模块，避免重复建设

- 六个 Video-Skills 负责 Setup/Grill/Spec/Tickets/Implement/Diagnose。
- 第七个 `video-change-impact-recovery` 提供基于规范化 Timeline 投影的离线影响范围/验证；不是 NodeTool API。
- `ai_director/runtime.mjs` 是本轮新增的**零网络、零付费**控制层；不会自动启动任何 MCP 或发送视频生成请求。

## M0 使用顺序

1. 外部 Agent 从真实 NodeTool MCP 枚举工具名、输入 Schema、用户权限和返回信息。不要根据官方文档直接填 observed。
2. 按现有 `STATE.json` 格式增补 `ai_director.timeline_id/tool_manifest/active_operation_id`；存储真实 ID，不生成演示值。
3. 调用 `capabilityMatrix(state)` 检查核心编辑工具。未通过就只做只读规划。
4. 已有工程修改：先用 `skills/video-change-impact-recovery/scripts/change_guard.py` 离线 plan；NodeTool 建立真实版本快照；再调用 `prepareOperation(state, request)` 通过准入。
5. **将返回的 STATE 先落盘**，之后由外部 Agent 调用现场发现的 NodeTool MCP 工具。收到回执后调用 `recordOperation` 并立即落盘。未知状态保持单写锁，不再提交同一个付费动作。
6. 真实 native readback/diff、NodeTool validate、完整渲染和多模态 QC 都必须做。最后仅用 `deliveryGate` 判断已收集证据是否完整；该函数不替代人工/模型检查。

`prepareOperation` **只验证调度门禁**，既不执行工具，也不判断内容质量。实时模型报价、Studio 运行状态、MCP Schema 和原生媒体 ID 必须由外部工具取得。

## 代码示例（不执行付费动作）

```js
import { capabilityMatrix, prepareOperation, recordOperation } from "../ai_director/runtime.mjs";
const capability = capabilityMatrix(state);
if (!capability.ready) throw new Error("NodeTool 缺真实工具证据: " + capability.missing.join(","));
// 在读取 NodeTool、取得真实快照、运行 change_guard、获费用批准后：
const prepared = prepareOperation(state, verifiedRequest);
// TODO: persist prepared as STATE.json BEFORE external MCP tool call.
// TODO: call discovered NodeTool MCP tool via actual runtime; DO NOT fabricate arguments.
// TODO: persist recordOperation(prepared, realReceipt).
```

## NodeTool 首次联调（零收费）

需要逐项验证：

| 类别 | 核查 |
|---|---|
| Tools | list/get timeline, edit/validate, create/restore version, render；实际名称、Schema 和权限 |
| Read | 工程及 Timeline ID、当前 revision、track/clip、素材引用 |
| Write | 隔离测试工程非收费修改、回读比对、恢复，且无并发写者 |
| Media | 本地媒体导入与播放、字幕/语音、可编辑时间线、导出文件 |
| External APIs | Provider 认证、提交、任务状态、成本界限；未知价格停止 |
| QC | ffprobe/ffmpeg 技术检查；视频理解接口对实际成片可用 |

若现有官方 MCP 工具名在运行版本发生变化，先改观察映射/工具清单，不要硬编码错误的请求结构。

## M0 CLI（不连接网络、不触发收费）

从仓库根目录执行：

```bash
node ai_director/cli.mjs capabilities /project/STATE.json
node ai_director/cli.mjs prepare /project/STATE.json /project/write-intent.json
# 外部 Agent 先持久化 prepared，再调用真实 MCP；之后记录回执
node ai_director/cli.mjs record /project/STATE.json /project/tool-receipt.json
node ai_director/cli.mjs delivery /project/STATE.json /project/evidence.json
```

`prepare/record` 写入同一个 STATE 文件，采用独占临时文件锁和原子替换；发生锁冲突时拒绝操作，不会自动覆盖或猜测已提交任务的结果。命令行程序不构建 NodeTool 原生请求、不校验自述证据真伪，也不代替人工审批。

## 测试命令

```bash
node --test ai_director/tests/runtime.test.mjs
python -m unittest discover -s skills/video-change-impact-recovery/tests -v
```

## 当前事实边界

- 已实现/离线自测：状态准入、工具观测、单写入、预算预留、未知任务锁定、交付证据门禁。
- 尚未实现：NodeTool MCP 自动发现/网络连接器、原生 Timeline 结构适配、视频生成任务客户端、全自动真实剪辑与视频质检。
- 验收时只能从真实工具回执升级状态，不能把设计文档或离线测试替代实机证据。
