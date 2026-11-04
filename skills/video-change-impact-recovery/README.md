# Video Change Impact & Recovery

这是供 Agent 使用的第七个独立 Skill，补齐 [Video-Skills v0.1.1](https://github.com/FlapPearLabs/video-skills) 在 NodeTool 时间线局部修改中的安全门禁。

**当前状态：可安装的 Skill 源码 + 可执行离线计划/回归校验 + 已文档化 NodeTool CLI 适配壳；没有声称真实 NodeTool MCP 联调成功。**

## 能做什么

- 修改镜头前从真实工程抽取规范化投影，分析镜头、配音、字幕、转场的依赖和允许修改字段。
- 模拟第三镜从 5 秒到 7 秒后，后续镜头及带有明确同步锚点的配音字幕调整，检查是否意外修改无关对象。
- 对未知音画锚点、重复 ID、环依赖、锁定对象、重叠主轨、版本漂移执行 fail-closed 阻断。
- 通过官方 NodeTool CLI 先创建版本快照、校验真实 native timeline，必要时恢复历史版本（**须先现场安装和确认**）。
- 候选 take 不自动晋升；最终仍需 NodeTool 原生校验、真实画面与音频试听。

## 安装

将 `video-change-impact-recovery/` 目录复制到你的 Agent Skills 目录（如仓库 `skills/video-change-impact-recovery/`），确保 `SKILL.md` 位于该目录根部；重新加载 Agent。现有六个 Skill 保留。将 `references/integration.md` 中的调用约定添加到 `video-diagnose` 和 `video-implement`。

可选 NodeTool MCP：Node.js 22+；按官方安装 `npx -y --package=@nodetool-ai/cli-mcp nodetool-mcp install`。安装后查看实际工具 Schema、做无付费结构测试。NodeTool CLI 需要本机真实安装，不能仅凭 MCP 安装命令保证 `nodetool` 在 PATH 中。

## 快速运行

```bash
python -m unittest discover -s tests -v
python scripts/change_guard.py inspect examples/timeline-normalized.json
python scripts/change_guard.py plan examples/timeline-normalized.json examples/intent-extend-s03.json --out /tmp/change-plan.json
python scripts/nodetool_cli.py probe   # 可选：要求本机已有 NodeTool CLI
```

`plan` 输出的 `candidate` 是**离线模拟的规范化投影**，不是 NodeTool 的可编辑文件。实际生产由 Agent 使用现场探测到的 NodeTool 工具写入，并根据 readback 生成 after 投影调用 `verify`；所有真实音画必须另做视听验收。

## 文件

- `SKILL.md`：Agent 执行规则与失败处理
- `scripts/change_guard.py`：离线影响分析、确定性模拟和越界修改校验（Python 标准库）
- `scripts/nodetool_cli.py`：保护的本地 NodeTool 快照、验证、恢复命令封装
- `references/nodetool-contract.md`：已核对官方能力与未确认边界
- `references/integration.md`：与六个 Video-Skills、SPEC/TICKETS/STATE 兼容方法
- `references/continuity.md`：音画同步、节拍、口型的验收规则
- `references/audit-schema.md`：事故恢复与审计证据要求
- `examples/`：同一六镜头广告规范化测试工程和三种改动
- `tests/`：固定规则回归测试

## 当前未完成

1. 你的 NodeTool 实际安装版本、MCP Tool Schema 与真实 timeline 回读适配。
2. NodeTool Native TimelineDocument 到规范化投影的具体字段自动转换（需用真实工程和 Zod schema 验证）。
3. 多层轨道/速度曲线/组合剪辑/高级转场的无损修改策略。
4. 真实付费生成、MP4 渲染、视听质量、口型/品牌连续性与真实回滚完整测试。

因此**不能说已经实现完全自主可靠修改**。这是一套优先可验证、可阻断误操作的 v0.1 基础。
