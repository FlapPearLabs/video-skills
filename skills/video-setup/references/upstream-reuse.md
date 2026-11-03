# 复用来源与边界

本套为原创中文领域适配；复用工作方法，没有复制上游执行代码或安装它们的依赖链。

| 上游 | 固定版本与已读文件 | 采用 | 调整/不采用 |
| --- | --- | --- | --- |
| [mattpocock/skills](https://github.com/mattpocock/skills) | 4ae2317ddb22b046e26455e4f9c9b3aaaf62212d；grilling、setup-matt-pocock-skills、to-spec、to-tickets、implement-spec、diagnosing-bugs 的 SKILL.md | 决策依赖、事实先查、讨论转规格、可验收的完整小任务、依赖就绪执行、可重复诊断 | 不复制 GitHub issue tracker、软件层次/TDD、每票独立工作树；保留三文件、串行画布写 |
| [sb-dev/video-production-skills](https://github.com/sb-dev/video-production-skills) | 5e82bb9a188d3cfc83cae0979cc39737011411b9；video-production、video-evaluate 的 SKILL.md 与 production/references/continuity.md | 最便宜的有效预演、人物产品场景锁定、selected≠approved、分离声音画面、完整动态检查、最小修复与两次尝试 | 不强制 Replicate/fal.ai、Node24/TypeScript、全套目录或自建图数据库；LibTV为主执行 |
| [alchaincyf/darwin-skill](https://github.com/alchaincyf/darwin-skill) | 8a8b66258e3c45d6ae4aea39719468c6428fcb0a；SKILL.md（自标v2.1）、references/runtime-neutrality.md | 九维结构审查、典型prompt测试、独立新上下文、成对比较、保留/回退、运行环境适配 | 不用绝对自评分证明质量；用户本轮已授权开发优化，可逆本地迭代持续做，创意/付费仍按实际项目授权 |

与上游相比：Grill每轮限1–3题以降低负担；不是要求每次重复六阶段。新证据优先于固定版本参考。
LibTV来源是用户提供报告，不是本会话直接读取官方 Schema。所用 API 必须现场重新加载。
Darwin 中的论文准确率、星数和“分数提升”没有在此项目独立复验，本包不将其当质量证据。
