# 兼容 Video-Skills v0.1.1 的集成合同

本 Skill 设计为 **第七个独立 Skill**，不替换原六项。参考仓库：https://github.com/FlapPearLabs/video-skills （读取到的是 2026-11-04 的 main，未修改远端）。

## 现有六 Skill 的责任边界

- `video-setup`: 查 NodeTool MCP/CLI 可用性、权限和收费；记录能力 `schema_only`/`observed` 等状态。
- `video-grill`、`video-to-spec`、`video-to-tickets`: 继续管理创意、已确认脚本、分镜、验收标准；本 Skill 不篡改已批准主创意。
- `video-implement`: 实际使用经验证的 NodeTool 连接器调用生成/编辑；本 Skill **不**作为新的生成工具或编辑器。
- `video-diagnose`: 判断不自然、口型/字幕/配乐错误；需要修改时先调用本 Skill 建立快照、约束范围与验收。

## 推荐增加的调用约定

在原 `skills/video-diagnose/SKILL.md` 的“提出最小改动”之后，新增：

> 如果实际修改 NodeTool timeline，先调用 `video-change-impact-recovery` 的规范化投影/plan/快照门禁；只有 guard 通过且已确认版本、预算后才能将方案交给 `video-implement`；执行完必须回读/verify/validate/render 视听再提交或回滚。

在原 `skills/video-implement/SKILL.md` 的“翻译 Ticket 为实际调用”之前，新增：

> 本 Ticket 如果是**已有 NodeTool 工程**的修改，必须取得 `video-change-impact-recovery` 计划与快照证据，严格遵守 allowed_fields；新生成资源先保存 candidate take，不得立即覆盖 active take。

## 与 STATE.json 的衔接

沿用 `STATE.json` 的 `approvals`、`assets`、`operations`、`budget`，不创建平行账本。每次成功回执立即更新以下信息；字段可放在对应 operation 下 `change_impact` 键，不要求改项目 schema 主版本：

```json
{
  "change_impact": {
    "base_manifest_sha256": "...",
    "plan_sha256": "...",
    "before_timeline_version": "from-real-NodeTool-receipt",
    "target_id": "S03",
    "allowed_fields": {"S03": ["asset_ref"]},
    "candidate_asset_ref": "asset://...",
    "after_manifest_sha256": "...",
    "native_validate": "passed|failed|not_run",
    "av_review": "passed|failed|not_run",
    "rollback": "not_required|verified|unverified"
  }
}
```

远端 ID、正式快照 ID 和本地哈希用途不同；切勿互换。保持旧的 `selected_output`、`previous_outputs`、历史操作、已花费和已预留预算。出现 version conflict 或提交状态 unknown 不允许盲重试。

## 正规化映射：最小必要字段

| 投影字段 | 来源要求 |
|---|---|
| `timeline_id` | 已读取的真实 NodeTool 序列 ID |
| `object.id` | 原生稳定 clip/track/字幕片段/beat-marker ID，不能靠数组下标 |
| `kind` | 从原生轨道类型、编辑关系推导；区分 voice 和 BGM |
| `start_ms` / `duration_ms` | 按项目时间基/FPS从真实时间读数换算，不作猜测 |
| `asset_ref` | 活跃 take 的稳定媒体引用；不要只用临时 URL |
| `deps` | 已核实的依赖；猜不到的标 unknown，先停写 |
| `sync` | `to/point/offset_ms` 由原生锚定/有证据的语音字幕关系支持；不能仅因时间重合猜测 |
| `locked` | 已批准保留或被其他用户锁定的对象 |

示例投影只适用于明确一条主视频轨、简单时间锚点的 30s 广告。多视频主轨、变速曲线、叠加层、嵌套组合、复杂转场、动态重定时需要单独建模，v0.1 默认不自动执行。
