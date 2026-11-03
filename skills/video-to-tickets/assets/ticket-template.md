## Ticket ID — 具体交付

- 类型与来源：asset/storyboard/animatic/shot/audio/subtitle/edit/qc/delivery；reuse/deterministic/generate。
- 用途与目标秒数：成片要解决什么、可检查输出。
- 前置依赖：真实阻挡的 Ticket ID。
- 输入：批准的 asset ID、源时间码、精确台词、SPEC 镜头 ID。
- 制作：起态→动作→终态、相机、音频；模型参数由运行时映射。
- 不变项：人物/产品/场景及相邻衔接。
- 验收：具体位置与方法；完整播放范围；技术要求。
- 失败：最小归属层、最大有效生成尝试2次、未改动素材的保留方式。
- 费用：已核实上限与单位或 unknown；批准范围；不能用任务批准代替预算批准。
- 节点映射计划：逻辑类型与边；实际 nodeId/taskId 运行后写 STATE，不杜撰。

正文后嵌入唯一 json manifest；字段见 references/project-contract.md。
