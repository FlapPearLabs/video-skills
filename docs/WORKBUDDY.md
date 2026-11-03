# WorkBuddy 安装与真实验收

当前只是 **v0.1.1 集成测试版**。切勿把本地测试当成真实商用成片验收。

## 安装

1. 使用仓库 `dist/Video-Skills-v0.1.1-WorkBuddy.zip`，解压它。
2. 在 WorkBuddy 技能管理中逐个上传 `workbuddy/` 中的六个单 Skill ZIP。
3. 先装 `video-setup` 并验证元数据、参考文件和 Python 脚本；通过后装其余五个。
4. 连接 LibTV 官方连接器并在 WorkBuddy 完成账户授权。不要把凭据写进项目 STATE。

## 非生成验收

1. 实际调用 `video-setup`，确认能读取 `project-contract.md` 中的「明确局部修改的批准继承」规则；不是只复述 SKILL.md。
2. 以 Skill 安装目录调用 `project_files.py --help`，不要依赖当前工作目录。
3. 在专用测试工程中以当前 Schema 创建非生成节点与连线，按项目图回读 `edges`。
4. 修改目标文本节点，验证不相关节点内容保持不变，记录 `revision.token`、`idempotencyKey` 与回执。
5. 在新的 WorkBuddy 会话中用项目 ID 再次读取，核对 STATE 与平台状态。
6. 检查 prepared → 实际调用 → 回执 → STATE 更新是否真实执行；若失败，保留 UNKNOWN 状态，不重复提交。

## 收费生成验收（单独授权）

只有在查看 LibTV 当前积分和模型价格并获用户授权后，才尝试：生成两段短视频 → 保存结果 → 只重做第二段 → 重新合成与视听检查。确认字幕、音轨和口型工具是否真的可用，不能根据接口名称推断。

详细原始验收标准见 `skills/video-setup/references/workbuddy-acceptance.md`。
