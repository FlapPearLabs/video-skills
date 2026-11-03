---
name: video-implement
description: "执行已确认的视频制作任务，通过 WorkBuddy 的 LibTV 原生连接器或现有媒体工具编排节点、处理素材、生成、合成与交付。用于从 TICKETS 制作视频、恢复中断任务、搭建非生成测试画布或按已批准预算执行单镜头。"
---

# 视频制作执行

先读 [项目约定](references/project-contract.md)、[LibTV 规则](references/libtv.md)、[质量规则](references/quality.md)。本技能不自带 LibTV 客户端；没有相应工具时只能准备本地计划。

## 执行

1. 读取三文件、批准证据和目标工程；核对 SPEC/TICKETS 当前哈希，按 blocked_by 找就绪任务。只有草稿时只做计划，不执行画布。用户授权的独立结构测试可不依赖商业脚本批准，但须明确测试范围。
2. 新会话先恢复：按 projectId 读工程，查询已知 taskId，核对节点/边/输出与未结操作。未知提交不重跑。当前 STATE 与平台不一致时先解释差异。
   尚无 projectId 且已授权创建时，按 create_project 当前 Schema 创建一次并立刻保存回执和 UUID；没有现存 revision 就记录“不适用”。提交结果未知时停止重复创建。这个启动路径与独立结构测试不走下面仅支持现存制作工程的 guard，但仍须遵守授权、幂等与默认不传 run。
3. 核对本次工具完整 Schema、权限、模型 inputContract 与费率证据。用 `python scripts/operation_guard.py STATE.json PLAN.json` 检查临时计划；它复用同目录的 project_files.py 检查项目结构与当前Ticket所用素材（不要求未来下游素材先获批），再检查计划与预算；不提交、不预留、不认证批准、不证明 Schema 或实时余额。
4. 在 STATE 落 prepared、预算预留与请求摘要。对同工程写入串行；重读 revision.token 后绑定 expectedRevision，稳定幂等键绑定同一 payload。默认不传 run。不要为适配脚本伪造报价或批准字段。
5. 翻译 Ticket 为实际调用：真实素材先复用；人物/产品/场景参考先锁；需要时先做低成本分镜与预演。结构回执与生成任务分开记录；taskId 立刻落盘，轮询遵守返回的节奏。
6. 每个实际产物先技术检查再完整视听；记录可用时间段、实际缺陷和 lineage。候选保留，用户选中/批准后才换正式引用；已有批准镜头先备份或保留旧节点。
7. 读真实时间线，计划并校验镜头顺序、in/out、音轨、字幕与时长，再提交必要改动。音频/字幕外部处理按既有工具完成，保留源画面。
8. 做 review render，展示实际样片与具体待审点。picture lock/交付批准缺失时不冒称 final；批准后按交付要求输出、QC、登记文件稳定引用。
9. 更新 STATE 进度。输出已做、证据、待审/阻塞、实际成本或 unknown；执行结果未通过时交 `video-diagnose`，不无限自动重试。

## 临时 PLAN

使用 `assets/operation-plan.json` 结构。`request` 是已经按真实 Schema 形成的工具参数；摘要是规范 JSON 的 SHA-256。
guard 只支持有 projectId/revision 的现存制作工程；不支持 create_project、未确认的独立结构测试或平台回执重放。不要为了让 guard 通过而伪造 projectId、revision 或审批。
`may_charge` 由实际工具行为决定；不止 run=true 会计费，音频/渲染/导出也检查。`project_id`、`ticket_id`、`operation_id`、idempotency_key 必须匹配记录。
执行一次后把相关预留保持到平台结算可核实；成功/失败都可能花费。脚本通过不允许省略预算记账。

## 失败分支

| 触发 | 第一处理 | 仍失败 |
| --- | --- | --- |
| guard 拒绝 | 读具体缺失记录，修正计划或恢复证据 | 不修改 guard 绕过预算 |
| 版本冲突 | 重读并核对差异，明确未提交才重新计划 | 不固定次数盲重试 |
| 提交超时 | 保存 unknown，查询 task/节点/原幂等回执 | 保留预算占用，停止新生成 |
| 第二次同诊断失败 | 复查参考/分镜/能力归属 | 展示证据请求决定，不再抽卡 |
| 字幕/合成能力缺失 | 用已有外部工具做确定性处理 | 缺必要工具则标交付阻塞 |

## 禁止

不要自动全图执行；不要覆盖未保存的批准素材；不要创建第二套 CLI 凭据；不要以模板字段猜测真实 API 参数。
不要把 schema_only/user_reported 写成 observed；不要把本地 guard、模拟测试或结构测试称真实视频端到端通过。

## 已授权的局部修订

用户明确的局部改词按项目约定“批准继承”执行：更新受影响文件的哈希并追加revision_evidence，保留未改素材批准、原预算上限和全部消费/尝试记录。只有超出原授权范围才请求新增批准；不得仅因文件哈希变化重复询问同一修改。
