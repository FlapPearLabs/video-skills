# LibTV 执行规则与证据边界

## 已知来源

来自用户提供的两份 WorkBuddy 报告，日期上下文 2026-11-01；本包开发环境无 LibTV 工具，未直接复验。
测试工程和节点ID仅保存在开发记录，不写入公开运行包。默认新建独立回归工程；用户明确授权时可使用其提供的Smoke Test工程，先记录原状态并只做限定修改。完整 revision/edge ID 没有提供，不能补全省略号。

| 内容 | 证据层级 |
| --- | --- |
| 创建工程、text 节点、空 video-clip、A→B 边、文本修改回读 | 用户报告实测 |
| 过期 revision 被 SNAPSHOT_REVISION_MISMATCH 拒绝且未写入 | 用户报告实测 |
| 不带 projectContext、只用 projectId 读取成功 | 用户报告实测，未实际新会话 |
| 真实生成、outputs、mediaPersistence、片段替换、付费与真实恢复 | 未验证 |
| 86 个工具可见、47 模型、41 完整 Schema | 当时报告，启动时重新发现所需工具 |
| 字幕门禁关闭、无 ASR/任务历史枚举/余额报价工具 | 当时部署发现，允许新证据更新 |

## 调用流程

1. 发现当前原生连接器、状态及目标工具。名称可能有命名空间前缀；按语义匹配。
2. 完整读取本次所用工具 Schema、模型 inputContract 和权限。此文不提供可直接发送的猜测参数。
3. 项目级读取节点与边。`read_node` 只读节点 data/position；关系读 `read_project(view=nodes).edges` 或 `get_project_snapshot(graph)`。
4. 单一写入者重读项目，取 **项目 `revision.token`**。不能用 `operationResult.graphRevision`，不能拿旧 Ticket 里的 token。
5. 保存 prepared 记录。所有可接受该字段的写调用带稳定 `idempotencyKey`；修改按 Schema 带 `expectedRevision`。
6. schema 不接受某个字段时不要擅自传参；确认幂等/并发替代保障，否则停下该写入。create_project 若无版本字段，记录基线不存在的事实。
7. 同一请求内容重试复用原 key；改变 payload 是新逻辑操作、新 key。版本冲突请求已明确拒绝后，重读、重比对，再用新 token 建立新操作。
8. 回执区分 `canvas_operation/cop_` 与生成 task。拿到 taskId 立即持久化；不要等视频完成才保存。
9. 回读精确字段与无关节点。`get_project_snapshot(section=issues)` 复用平台问题检查；MEDIA_OUTPUT_MISSING 只是结构阶段预期 warning，不能当画质检测。

## 版本冲突与断线

| 触发 | 第一处理 | 仍无法确认 |
| --- | --- | --- |
| SNAPSHOT_REVISION_MISMATCH | 重读 revision.token、目标节点与边，比较他人改动 | 报告冲突和差异；不循环盲写 |
| 已有 taskId | 用 task_status(task_id) 恢复查询 | 保留 unknown 和预算预留，不重新生成 |
| 提交超时、没有 taskId | 查目标节点/项目回执，确认幂等键是否可恢复原回执 | 不换 key；不默认可安全重放；请求平台/用户核查 |
| 新会话 | 读本地三文件，按 projectId 重读，比对 taskId/outputs | 不能找回时标恢复阻塞，不重新创建工程 |
| 超时但返回 canvas_operation | 回读目标内容判断是否生效 | 不把超时当明确失败 |

## 模型与费用

用户报告 wanx3.0 / wanx3.0-prime 当时最低 2s、480P、非会员可用；这些不是实时目录，也不是报价。
调用时查询真实模型契约，不硬编码模型名、分辨率大小写或时长。
报告中的单段重拍 4–30 秒/24fps 属特定编辑路径，不能套用到所有模型。
无余额/报价接口时写 unknown，等待控制台可核实证据。没有收费生成不等于已核对账单免费。

## 保存、候选和时间线

修改前记录目标与依赖子图及所有选中媒体稳定引用。优先复用已有产物。
已批准产物若不能证明持久/可回退，先下载保存并算哈希，或创建候选节点保留旧节点；两种都做不到时停止覆盖。
可原地修改尚未批准的测试文本；真实输出是否保留必须现场核对，不能从文本节点测试推断。
修改指定节点后只重建受影响的下游合成，不执行全图。
时间线先读真实片段与音轨，再使用 `apply_timeline_edit` 的 plan/校验能力；确认计划只影响目标片段后再按实际 Schema 提交。
`edit_video_selection` 的 replace 只在其契约与素材满足时使用。禁止猜测片段索引或把生成时长当时间线 out 点。
字幕若仍关闭，转既有 FFmpeg/字幕工具；音频和字幕改动不得因此重跑源画面。
