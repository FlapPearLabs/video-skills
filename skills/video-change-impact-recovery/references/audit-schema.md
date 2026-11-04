# 变更事务审计要求

原 `STATE.operations` 记录付费与幂等状态，本 Skill 只加 `change_impact` 扩展（见 `integration.md`），不另起数据库。

每次事务保存下面的证据，敏感值不得出现：

1. 事务 ID、工程/时间线 ID、用户请求原话、批准来源。
2. 开始前原生 timeline 文档的可恢复引用、规范化投影 SHA256、`revision`/版本、active take、素材哈希或稳定 ID。
3. plan 的 SHA256、target、predicted diff、allowed fields、check-only/关联对象、blocked/warnings。
4. 真实 NodeTool `create_timeline_version` 返回的快照版本 ID。只有本地文件不记作远端快照成功。
5. 改动调用的工具名、输入 payload 摘要、回执、task ID、可能计费情况（预算按原合同）。超时和未知提交保留 unknown。
6. 实际 readback 与预期的逐字段 diff；NodeTool 原生 validate 结果；试听/口型/转场/音乐卡点检查项与证据。
7. `committed|rolled_back_verified|rollback_unverified|blocked` 和引用；若恢复失败，禁止声明已完全回滚。

**不要保存**：API Key、会话令牌、无关的客户数据、未经许可的原始素材副本。

推荐日志：项目现有临时目录 `tmp/change-impact/<transaction-id>/plan.json`、`native-before.json`、`native-after.json`、`verify.json`、`evidence.md`。在 `STATE.operations` 中只存稳定索引，不复制完整工程。
