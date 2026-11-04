---
name: video-change-impact-recovery
description: "对 AI 视频工程的局部修改执行影响范围分析、时间线/音频/字幕联动检查、差异预演、快照、最小写入、视听回归与失败回滚。只要用户要求改镜头、重生成片段、延长/缩短时长、改口播字幕、配乐卡点或转场，尤其使用 NodeTool MCP/CLI 与现有 Video-Skills 时，都必须先运行本 Skill 的变更保护流程；不要重做整片。"
---

# Video Change Impact & Recovery · v0.1

作用：为现有 `video-diagnose`、`video-implement` 增加一层**修改事务保护**，而不是新剪辑器。用户只决定创意、参考方向、脚本和超范围授权；Agent 负责分析、操作、核验、恢复。

## 触发与入口

- 用户说“只改第 3 镜”“延长两秒”“换配音/字幕”“改运镜/转场”“音乐卡点没对齐”“不要动其他镜头”时触发。
- 新制作流程仍走 Setup→Grill→Spec→Tickets→Implement；已有工程修改时走 Diagnose→**本 Skill**→Implement→Diagnose 视听验收。
- 每次写操作只处理一个变更事务；不同 Agent 不得并行写同一 timeline。
- 先读 `references/integration.md`（与现有项目记录合并），首次接入 NodeTool 读 `references/nodetool-contract.md`，碰到声画/延长镜头读 `references/continuity.md`。

## 强制执行顺序（fail closed）

1. **确认真实工程**：从当前 NodeTool `get_timeline`/同等读取工具获取 `timeline_id`、原始 timeline 文档、当前版本信息、轨道、已选 take、相邻镜头、音频、字幕；从现有 `SPEC.md`、`TICKETS.md`、`STATE.json` 读取授权、预算和资产 lineage。只读部分不需要新增授权。
2. **建立规范化投影**：把相关对象映射成 `examples/timeline-normalized.json` 所示的 `schema_version=1.0` 格式。该结构**不是 NodeTool 原生 JSON**，不得直接发送给 NodeTool。必须从实际文档读取 ID/时长/锚点。分不清音频依赖、转场或多轨语义时标为 unknown，停止自动写入，先核实。
3. **确定最小目标**：写出修改类型、目标 ID、旧值/新值、允许受影响范围。用 `scripts/change_guard.py plan` 输出预测变更、依赖闭包、超范围阻断与视听检查项；从真实 NodeTool 版本/源文件对映到原生操作。禁止凭自然语言臆造原生操作参数。
4. **预算与权限复用**：沿用原 `STATE` 的批准哈希、revision_evidence、操作账本、调用数、spent/reserved，不清零。不因为局部改词再问已授权的事情。新的付费 API 调用、超额、改核心创意或扩大镜头范围仍需明确审批。
5. **快照**：修改正式工程前用 NodeTool `create_timeline_version` 或已安装 CLI 的 `timeline versions create` 创建真实快照，保存成功回执及版本 ID。只有文件副本没有 NodeTool 快照，不得宣称可恢复线上工程。对生成操作先产生 inactive candidate take，旧 take 保持 selected。
6. **执行**：独占写锁、重读当前文档并重新对比 base/revision；冲突停止，重新分析。优先按原生 `edit_timeline`/`apply_take` 的**现场工具 Schema**逐步写入；该版本缺能力时使用已验证的工具路径，不能假设字段名称。每次提交记录 `operation_id`、payload 摘要、task id、是否可能收费、收到的回执。未知状态不重新发送生成请求。
7. **双重核验**：A) 导出修改后真实 timeline 并转换同一规范化投影，运行 `change_guard.py verify`；再用 NodeTool `validate_timeline` 或 CLI validate 验证原生文档。B) 预览前后切点、实际音轨、字幕、音乐高潮、尾部结束点和受影响的动作/口型；确认 `complete`、导出与媒体链接可用。静态校验通过**不等于**音画/审美通过。
8. **提交或回滚**：仅两层验证通过且未破坏批准内容时，选用候选 take 并持久化 `STATE`。失败时保留失败候选和证据，尝试 NodeTool `restore_timeline_version`（或已确认快照的 CLI restore），再回读并重新校验；未实际恢复成功只能报告 `rollback_unverified`。平台快照只覆盖 timeline：资产仓库、外部账单、远端生成任务和 SPEC/TICKETS 必须分别保持记录，不声称全部事务回滚。

## 三种常用变更（本地确定性模拟）

```bash
# 1. 换镜头 S03，但保持时长不动
python scripts/change_guard.py plan examples/timeline-normalized.json examples/intent-replace-s03.json --out /tmp/change-plan.json
# 2. 第三镜从 5 秒改成 7 秒：后续镜头和有 sync 锚点的字幕/配音才会同步移动
python scripts/change_guard.py plan examples/timeline-normalized.json examples/intent-extend-s03.json --out /tmp/change-plan.json
# 3. 模拟结果核验（注意：candidate 是模拟投影，实际写入后需换成真实 readback 投影）
python -c 'import json;from pathlib import Path;p=json.loads(Path("/tmp/change-plan.json").read_text());Path("/tmp/candidate.json").write_text(json.dumps(p["candidate"],ensure_ascii=False))'
python scripts/change_guard.py verify examples/timeline-normalized.json /tmp/candidate.json /tmp/change-plan.json
```

**三条限制**：本地脚本不修改 NodeTool；规范化投影不验证真实口型、动作或音乐节拍；一个变更改变镜头时长但无法核实音画时间锚点时，不得自动 ripple。

## 失败/升级策略

| 触发 | 行动 |
|---|---|
| 依赖缺失、重叠轨道、多机位、绝对时间音频无法归属 | `blocked`；读原生轨道与同步来源，补证据后重新计划 |
| 额外镜头/原批准素材需要修改 | 不自动批准；将明确受影响范围展示给用户 |
| 生成任务未知、网络超时 | 记录 unknown/taskId；只查询，不重复付费提交 |
| 任意未批准字段变化 | 禁止提交选中 take；恢复原快照并记录对比 |
| timeline 验证成功但试听/连续性失败 | 候选不晋升，修局部或恢复 |
| 恢复接口不存在或恢复失败 | 保持 `rollback_unverified`，停止进一步写入 |

## 最小输出

对用户只报告：改了哪里、连带移动了什么、保留了什么、实际验证结果，以及是否需要新增预算/创意审批。详细 diff、哈希、tool 回执、旧/新 asset ref、快照 ID 放现有 `STATE.operations` 或项目临时审计文件，不刷屏。审计样例见 `references/audit-schema.md`。

## 自测与边界

```bash
python -m unittest discover -s tests -v
python scripts/nodetool_cli.py probe
```

`nodetool_cli.py` 仅封装官方文档列出的本地 CLI `timeline validate`、`versions create/restore`；它不会编辑 Native Timeline，也不自动调用视频生成 API。连接真实 NodeTool MCP 时必须现场发现工具/Schema；不要把离线测试写成真实联调。
