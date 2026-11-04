# NodeTool 适配与能力证据（2026-11-04 查询）

## 已在官方文档确认的能力（**尚未在用户本机联调**）

- 文档：https://docs.nodetool.ai/ai-timeline-editing.html — 生成结果作为 clip 的 take；切换 take 不改变开始时刻、时长、轨道、效果；`ui_timeline_generatively_edit_clip` 创建候选但不会自动替换 active take。
- 文档：https://docs.nodetool.ai/harnesses — `validate_timeline`, `list_timelines`, `list_timeline_versions`, `get_timeline_version`, `create_timeline_version`, `restore_timeline_version`, `edit_timeline`, `generatively_edit_clip`, `apply_take`；`apply_take` 回执带 `undo_version`；`get_clip_frames` 与音画确认需核查 `complete`；`timeline debug` **不模拟真实解码和生成**。
- 文档：https://docs.nodetool.ai/cli — `nodetool timeline validate <id-or-file> --json [--warnings-as-errors]`，`nodetool timeline versions create <id> --name ...`，`nodetool timeline versions restore <id> <version>`；版本恢复后再次验证。
- 文档：https://docs.nodetool.ai/api-reference.html — tRPC `timeline` 路由中有 `get/list/update/versions.create/versions.restore`，但读写 payload 是 Zod Schema/运行时具体定义，不能猜 HTTP 请求体。
- 文档：https://nodetool.ai/mcp — NodeTool MCP 可用于 Agent 生成图片、视频和操作 timeline；连接需本地有 Node.js 22+，`npx -y --package=@nodetool-ai/cli-mcp nodetool-mcp install`。

## 现场适配步骤

1. 连接 MCP 后枚举**真实**可用工具，查看各工具的完整 `inputSchema`、返回模式、认证用户、权限、服务版本。确保 `list_timelines` 与取一个 timeline 的只读能力可用，核对当前项目 ID。
2. 测只读调用：获取 storyboard/shot/timeline、track/clip/asset、同步来源与版本；把真实文档保存在项目临时目录（不要把密钥或私人素材提交仓库）。无法取得分镜→timeline 关联时只做 timeline 级分析。
3. 测可逆结构修改：建立测试 timeline，建立真实快照、做一次**非付费**变更、读回、validate、restore、读回。不得在用户付费项目上试探接口。
4. 在成功验证前，禁止调用 `apply_take` / 大范围 `edit_timeline`。实际输入字段须以当前工具 Schema 为准；本文只提供工具名称，不提供猜测参数。
5. 若 CLI 已安装，可运行 `python scripts/nodetool_cli.py probe`。需要真实快照时，核对 ID 后设置 `NODETOOL_ALLOW_MUTATION=yes` 并执行 `snapshot <real_id>`；恢复时必须同时提供快照 ID 与 `--confirmed-timeline-id`。脚本不自动接受演示 ID。
6. NodeTool 的资产 take/素材可能存于独立资源存储；恢复 timeline 并不等于删除已付费生成或恢复远端生成额度。

## 不应承诺

- 不承诺任何 NodeTool 版本提供所有已文档化工具；缺工具时降级或停止写操作。
- 不承诺 `validate_timeline` 能检查节奏、配乐卡点、口型、完整音乐和品牌一致性。
- 不承诺所有第三方异步视频 API 可以直接通过 NodeTool Custom Provider 连接；需独立适配并验收。
- 本 Skill 没有替用户连接 NodeTool、执行实际生成或恢复操作。
