# AI Director · M0 产品控制层

本目录是 Video-Skills 的产品功能实验区，**不是已完成的 NodeTool 导演工作站**。

- `runtime.mjs`：不访问网络的状态与权限门禁；复用项目 `STATE.json` 的预算与操作记录。
- `tests/runtime.test.mjs`：合成状态安全回归测试。
- 产品规范：[`docs/AI_DIRECTOR_PRODUCT_SPEC.md`](../docs/AI_DIRECTOR_PRODUCT_SPEC.md)
- 联调步骤：[`docs/AI_DIRECTOR_IMPLEMENTATION.md`](../docs/AI_DIRECTOR_IMPLEMENTATION.md)

## M0 能做什么

- 核验工具记录是否包含真实观测证据（不能核验证据是否真实）。
- 为已有 timeline 的变更要求真实快照、Change Impact 计划、允许字段和当前版本。
- 检查单写入者、幂等、已批准任务和费用上限；记录 prepared/submitted/unknown/succeeded 等状态。
- 不确定任务提交结果时保留费用预留并锁住新写入。
- 拒绝没有可引用证据的「已交付」声明。

## 不能做什么

不会自动连接 NodeTool、发现 MCP 工具、执行 Timeline 修改或渲染视频；不会替代视听质检。真实编辑调用需后续集成，并以现场工具 Schema 为准。

## 命令行入口

`node ai_director/cli.mjs capabilities|prepare|record|delivery STATE.json [request.json]`。其中 `prepare/record` 只修改本地 STATE，不操作 NodeTool。参见 [联调说明](../docs/AI_DIRECTOR_IMPLEMENTATION.md)。

## 运行测试

```bash
node --test ai_director/tests/runtime.test.mjs
```

Node.js 22+ 建议；无需安装第三方依赖。

**安全顺序：** 完成真实读取 → 运行 change_guard → 保存 NodeTool 快照 → 准备操作并持久化 STATE → 调用实际 MCP → 保存真实回执 → 回读原生工程 → 实际渲染/QC → 交付门禁。
