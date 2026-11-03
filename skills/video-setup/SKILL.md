---
name: video-setup
description: "检查视频创作环境、现有工程、权限、模型输入契约、计费边界和恢复记录，建立最小项目。用于开始 AI 视频项目、切换设备或会话、检查 WorkBuddy/LibTV 连接器、确认工具能否完成分镜与局部修改。"
---

# 视频环境检查

先读 [项目约定](references/project-contract.md) 与 [LibTV 规则](references/libtv.md)。当前工作目录不是默认视频项目；先定位用户指定项目，已有工程优先恢复。

## 执行

1. 读取已有三文件与素材引用。不存在时用 `python scripts/project_files.py init PROJECT --profile restaurant` 创建草稿；已有任何核心文件时脚本拒绝覆盖。四种 profile 见 `--help`。
2. 发现可用视频/图片/配音/素材/播放/FFmpeg 工具，核对当前连接状态、权限与必要 Schema。没有连接器仍可进入创意、规格、任务阶段，记录执行阻塞。
3. 仅对当前项目做只读探测：项目 UUID、revision.token、节点、边、时间线、issues、所需模型 inputContract。没有项目不为检测而自动创建；已获结构测试授权时用独立测试工程。
4. 在 STATE.capabilities 记录每项证据等级、范围和时间。把用户报告中的结构证据与现场结果分开；余额、报价、字幕、ASR、outputs、局部替换、恢复没有证据就写 unknown。
5. 确认素材可读取、稳定引用可恢复、音画能实际审查。探测 ffmpeg/ffprobe 只查可用性，不自动安装依赖。
6. 输出四类结果：已观察通过、仅接口/报告支持、不可用、未验证。给出可进行的下一阶段和所缺的最小证据。更新 STATE.stage=setup。

## 检查与交接

`python scripts/project_files.py check PROJECT` 检查文件与依赖；加 `--ready` 检查 SPEC/TICKETS 的实际批准和哈希及全部任务素材就绪；这是整份计划的就绪检查，不能据此阻挡只用已批准素材的当前任务。
脚本输出只代表本地记录合法，不证明平台调用和内容效果。使用技能所在绝对目录解析脚本；不要假设进程 cwd 是技能目录。
输出：三文件、当前能力证据、执行阻塞。用户已给完整创意时交 `video-to-spec`；否则交 `video-grill`。

## 失败分支

| 触发 | 第一处理 | 仍失败 |
| --- | --- | --- |
| 未连接/无权限 | 确认工具返回与目标账号/工程，记录 blocked | 保留离线创意工作；只要求恢复缺失连接，不探测其他账号 |
| projectId 可读但本地缺记录 | 回读目标工程与用户明确引用 | 不按相似名称认领客户工程 |
| Schema 与旧报告不同 | 更新能力证据，按当前契约规划 | 不凭旧字段写入 |
| 费用不可核实 | 继续非生成准备，记录费用 unknown | 暂停可能计费操作 |

## 禁止

不要以 vip:false 推断免费；不要把只用 UUID 读取成功写成严格跨会话通过；不要修改现有客户项目做烟雾测试。
不要以安装 CLI 掩盖平台缺口。只有证明必要操作缺失且 CLI 能补齐时才提出补充。

## 维护与真实验收

修改本套时读 [上游复用记录](references/upstream-reuse.md)。在目标环境验收时读 [WorkBuddy真实验收](references/workbuddy-acceptance.md)，严格区分已执行记录和待执行步骤。

继续维护或评估时读 [验证记录](references/validation.md)，其链接保留提示词、原始回答和判断证据。不要把首轮对照中的局部优势扩展为普遍质量提升。

## WorkBuddy 适配与维护

维护发布时读取 [发布规则](references/release.md)。共享约定以本技能references中的project-contract.md、quality.md、profiles.md、libtv.md和scripts/project_files.py为权威源；用scripts/build_release.py --sync分发到独立技能，再分别保存更新。普通视频制作不运行发布脚本。

WorkBuddy真实导入后，先完成资源读取检查：明确读取本技能目录的references/project-contract.md，报告其中“明确局部修改的批准继承”小节标题和三文件名；再以本技能实际目录定位scripts/project_files.py，仅执行--help。没有真实读取或命令回执时保持未验证，不凭SKILL正文复述当通过。

本次修订证据见 [v0.1.1验证记录](references/v0.1.1-validation.md)，继续维护时再读取其审查/前向执行原文。
