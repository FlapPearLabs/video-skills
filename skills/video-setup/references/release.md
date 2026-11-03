# v0.1.1 发布与目标环境验收

## 权威来源与兼容边界

2026-11-01核对官方页面：
- https://open.workbuddy.cn/docs/skill —— 开放平台市场发布要求中英文展示/描述、version、author，补充资料使用@references/文件名。
- https://www.workbuddy.cn/docs/workbuddy/From-Beginner-to-Expert-Guide/Function-Description/Skills-Market —— 客户端支持添加技能→上传技能；该页面没有给出相同完整元数据要求，也未承诺多Skill ZIP的批量导入行为。

因此只称“按已公布的开放平台格式生成并做本地检查”，不称“客户端导入已通过”。agents/openai.yaml不能替代WorkBuddy元数据。

## 构建

先定位本技能实际目录，再运行：
`python scripts/build_release.py --skills-root PERSONAL_SKILLS_ROOT --out OUTPUT_DIR --author AUTHOR --version 0.1.1 --sync`

PERSONAL_SKILLS_ROOT是包含六个已安装技能的实际目录，不是项目素材目录；脚本按frontmatter名字解析，不依赖生成的目录ID。发布辅助脚本依赖PyYAML；运行包的项目/操作检查只用Python标准库。

权威共享源：本技能references/project-contract.md、quality.md、profiles.md、libtv.md与scripts/project_files.py。
--sync将它们分发到相应独立技能；没有--sync时发现漂移立即拒绝构建。维护时修改权威源，用脚本分发，分别保存技能修改；不要手工改六份后假设一致。

## 两种交付

- WorkBuddy集合：解压后workbuddy内有六个独立ZIP；每个ZIP只包含一个技能目录和全部运行依赖，元数据已适配，引用为@references/...，资产模板放templates。先单独导入video-setup，核对真实资源读取，再导入其余技能。
- development包：保留通用Agent Skills格式的原始六技能、源码、测试和历史评估证据。此包是开发资料，不作为单技能市场上传包。

运行包不包含个人Smoke Test UUID、测试脚本、大量离线评估、上游审查或发布器；没有建立新的MCP或CLI适配器。公共接口缺口仍需连接器/已有媒体工具解决。

## 本轮验收范围

本轮能检查：字段/版本、引用可达、独立ZIP结构、运行依赖完整、导出脚本的相对路径、Python语法、内容隐私筛选、共享副本一致与局部审批继承回归。
本轮没有LibTV工具或WorkBuddy客户端会话：安装UI、@references实际自动读取、prepared→真实节点修改→回执→STATE、真正新对话恢复都保持未验证。
guard仍为只读预检，本版未增加事务执行器，也不因字段合法声称真实调用不会丢记录。
下一步按workbuddy-acceptance.md先完成真实非生成联调，再根据是否实际漏记决定是否增加小型原子写入辅助函数。
