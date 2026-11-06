# AI Director M1：NodeTool 联调观察

以下是隔离的 Windows 本地测试，NodeTool CLI/MCP 0.8.10，Node.js 24.22.1。测试使用合成媒体和独立数据库；它不是产品验收。

## 已观察

- 外部 MCP 客户端可以连接 stdio 服务，发现 `execute_code`、`upload_asset`、`download_asset`；时间线能力经 `nodetool.searchTools` 发现，不是平铺 MCP 工具。
- 在隔离数据库创建时间线，上传三段两秒视频和六秒音轨，通过 `edit_timeline` 添加四个媒体片段和三个文字片段：七个操作回执均成功。回读显示三条轨、七个片段、六秒时长；对已保存时间线的原生 `validate_timeline` 返回无错误。
- 可以创建原生版本，并通过 `get_timeline_version` 读取快照。回执仅说明时间线快照已保存，不包含素材文件或远程任务的回滚。

## 仍需处理

- `render_timeline` 首次调用返回工作流缺少节点包；已在包目录中定位 `nodetool.timeline.RenderTimeline` 属于 `video`。节点包安装和 MP4 渲染尚待完成，未进行视听验收。
- 实际回读中轨道的 `id` 被缩短为 12 字符，片段的 `trackId` 保持完整。将 `get_timeline_version` 的 `document` 原样传给 `validate_timeline` 返回七个 `clip_track_missing` 错误。即使在 `execute_code` 内提取 ID，返回的轨道 ID 仍为短形式。因此不能假设回读文档可无损用于 `set_timeline_document`；适配层须在确证完整、唯一映射及所有引用后才允许整文档写入，否则拒绝。不得仅凭时间线静态校验通过就声称回读结果能安全写回。
- 第二镜替换的离线影响计划已根据测试工程构建；原生修改、差异验证、快照恢复和恢复后的回读尚未完成。
- 生产适配层、严格收费操作分类和端到端幂等恢复尚未完成。测试脚本与媒体位于隔离工作目录，不属于可交付的仓库适配器。

以上是特定版本和环境的观察，升级 NodeTool 后应重新发现 Schema 并复测。
