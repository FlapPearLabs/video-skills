# Video Skills

**在 WorkBuddy / Codex 里，用 Agent 制作和修改 AI 视频。**

从创意讨论、参考素材选择，到脚本、分镜、LibTV 节点执行、样片审查和局部修改，尽量交给 Agent。用户负责提出目标、选择创意、批准关键方案和验收成片。

当前版本：**v0.1.1 · WorkBuddy 集成测试版**。六个 Skill 的静态检查与本地测试通过；**尚未验证 WorkBuddy 客户端实际导入、LibTV 真实视频生成、口型修复或商业交付效果**。不要把它当作已完成的全自动视频生产服务。

## 适合什么场景

| 制作场景 | 输入 | 重点 |
|---|---|---|
| **探店** | 门头、店内、菜品或服务素材、参考视频 | Hook、A-roll / B-roll、真实卖点、节奏与 CTA |
| **探厂** | 厂房、设备、产品、工艺信息 | 产品与工艺真实性、工业运镜、解说 |
| **创意营销** | 产品图、品牌要求、创意参考 | 概念、转场、故事、画面节奏与预演 |
| **数字人** | 已授权人物参考或生成角色、台词、声音 | 人物一致性、配音、口型、镜头复用 |

四种场景共享同一套 Skill；它们是制作预设，不是四套独立系统。

## 六个 Skill

| Skill | 作用 |
|---|---|
| [`video-setup`](skills/video-setup/SKILL.md) | 核对连接器、工具、素材、权限、生成费用和恢复状态 |
| [`video-grill`](skills/video-grill/SKILL.md) | 讨论创意，比较人物、场景、镜头候选，记录你的选择 |
| [`video-to-spec`](skills/video-to-spec/SKILL.md) | 固定脚本、参考资产、分镜、声音、交付要求 |
| [`video-to-tickets`](skills/video-to-tickets/SKILL.md) | 拆成可验收的镜头、素材、声音、字幕和剪辑任务 |
| [`video-implement`](skills/video-implement/SKILL.md) | 按实际工具契约执行 LibTV 画布操作、生成与合成 |
| [`video-diagnose`](skills/video-diagnose/SKILL.md) | 定位问题，优先修指定镜头、字幕或音频，并检查关联影响 |

简单需求不强迫走完所有阶段；多镜头广告可按 `Setup → Grill → Spec → Tickets → Implement → Diagnose` 工作。

## 安装到 WorkBuddy

> **前提**：WorkBuddy 已安装并有可用的 LibTV 官方连接器。连接器需要使用者自行授权。视频生成是否扣积分，由当前账号、模型、任务与平台计费规则决定。

1. 下载本仓库的 [`dist/Video-Skills-v0.1.1-WorkBuddy.zip`](dist/Video-Skills-v0.1.1-WorkBuddy.zip)，**解压外层 ZIP**。
2. 打开 WorkBuddy 的技能管理/添加技能/上传技能功能。
3. 先导入 `video-setup-v0.1.1.zip`，确认能识别 `SKILL.md`、读取其 `references/project-contract.md` 并运行 `project_files.py --help`。
4. 再逐个导入余下五个独立 ZIP。不要把外层合集当成单个 Skill 上传。
5. 进入项目，先运行 `video-setup`；需要制作时进入 `video-grill`，已经确认方向时可直接整理 SPEC。

每个独立安装包见 [`dist/workbuddy/`](dist/workbuddy/)。详细检查顺序见 [WorkBuddy 安装与验收](docs/WORKBUDDY.md)。**WorkBuddy 实际导入尚未在此版本验收**。

## 在 Codex / 其他兼容 Agent 中使用

本仓库的 [`skills/`](skills/) 保存通用 Agent Skills 格式源文件。可将需要的 Skill 目录复制到对应 Agent 的 Skill 目录，按该客户端实际规则重新加载；**本项目尚未实测所有客户端的识别与自动路由方式**。

源码的 `SKILL.md` 使用通用 frontmatter；`dist/workbuddy/` 中的包含 WorkBuddy 发布适配元数据和资源引用。

## 第一次制作示例

> 「帮我做一条 20 秒探店视频。我会上传门头、店内和菜品的照片。先用 video-grill 给出两三个具体的创意方向，我选定后再制作分镜和样片。不要直接运行收费生成。」

制作过程中，Agent 根据需要维护三个项目文件：`SPEC.md`（制作规范）、`TICKETS.md`（镜头任务）、`STATE.json`（工程、节点、任务、批准与预算状态）。实际素材保存在用户指定位置或原生平台，不把私人素材和令牌提交到本仓库。

修改示例：

> 「第 2 个镜头的人物动作不自然，保留配音和其他镜头，只重做这一段。先列出会影响的节点和预计费用。」

## 工具边界与安全规则

- **WorkBuddy + LibTV** 是 v0.1.1 首选执行路线；不强制安装额外 LibTV CLI、Blender、ChatCut、CapCut 或口型服务。
- 项目图关系应从项目级 `graph/edges` 读取；不可把 `read_node` 当成完整依赖图。
- 修改时使用项目 `revision.token` 作为 `expectedRevision`；不能与 `operationResult.graphRevision` 混用。
- 写入需要稳定 `idempotencyKey`；出现版本冲突时先重新读取，不盲目覆盖。任务提交状态未知时不重复扣费提交。
- **没有明确授权的收费操作默认禁止**。`vip:false` 不等于免费；实际费用与账号余额需在平台确认。
- 资产/制作方案/样片需要相应审批；用户明确批准的局部改动可继承未受影响的批准，但不能因此扩大花费范围。
- 字幕、ASR、口型或精细剪辑接口不完整时可调用现有媒体工具；没有实际能力就标注阻塞，不声称已经交付。

## 测试与当前状态

```bash
python skills/video-implement/scripts/test_local_records.py
python skills/video-setup/scripts/test_release.py
```

本次源码来自 v0.1.1 开发包，本地记录测试 **37/37**、发布测试 **10/10** 为既有验证范围。它们**不证明**真实视频生成、人物一致性、成片质量或跨会话完整恢复。

| 能力 | 目前的证据 |
|---|---|
| 六个 Skill 的文件与发布包 | 静态检查通过 |
| 项目记录、预算门禁、审批继承 | 本地回归测试通过 |
| LibTV 创建/读取/修改无生成节点 | 用户提供的 WorkBuddy 结构测试报告证实；发布包尚未真实联调 |
| WorkBuddy 真实导入与 Skill 资源加载 | **待验证** |
| 视频、配音、字幕、口型与局部重做 | **待真实素材和可用额度验证** |

若运行后发现真实缺口，优先修正具体 Skill 或调用路径，不重新开发独立画布、VideoGraph 数据库或视频制作平台。

## 项目结构

```text
skills/                         # 六个可维护的 Agent Skill 源码
  video-setup/
  video-grill/
  video-to-spec/
  video-to-tickets/
  video-implement/
  video-diagnose/
dist/                           # WorkBuddy 独立 ZIP 与整套下载包
docs/WORKBUDDY.md               # 安装及实测验收说明
RELEASE.json                    # 发布版本与安装包摘要
```

## 来源与署名

这套 Video Skills 是针对视频制作工作流的中文实现，借鉴但不冒充以下项目的官方插件或产品：

- [Matt Pocock — Skills](https://github.com/mattpocock/skills)：Grill、Spec、Tickets、Implement、Diagnose 的工作方法。
- [Video Production Skills](https://github.com/sb-dev/video-production-skills)：素材一致性、镜头、评估与修复方法。
- [Darwin Skill](https://github.com/alchaincyf/darwin-skill)：Skill 的迭代评估方法。
- [LibTV](https://www.liblib.tv/)：外部视频生成与原生画布平台，须自行配置并遵守其服务条款。

详见 [`upstream-reuse.md`](skills/video-setup/references/upstream-reuse.md)。**这是社区项目，不是 Matt Pocock、LibTV 或 WorkBuddy 的官方联合产品。**

## 许可证

此源包未附带明确的开源许可证，暂不声明 MIT 或其他授权。公开发布和二次使用规则应由仓库所有者明确后增加 `LICENSE`；第三方项目保留各自权利。