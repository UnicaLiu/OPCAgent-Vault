---
title: "Task Config Snapshot 规范"
type: "rule"
tags: ["task", "config-snapshot", "规范", "冻结参数"]
created: 2026-06-14
version: "1.0"
status: "active"
---

# Task Config Snapshot 规范

> 定义 OPCAgent 任务创建时 config_snapshot 的完整字段结构。
> 快照在任务创建时冻结，确保历史任务可复现。

---

## 设计原则

| 原则 | 说明 |
|------|------|
| **创建时冻结** | config_snapshot 在任务创建时写入，之后不再修改 |
| **完整可复现** | 包含重现任务所需的所有参数，不依赖外部配置的"当前值" |
| **最小必要** | 只冻结此任务需要的参数，不冻结全局配置 |
| **快照优先引用** | 记录快照本身的值，不只是引用 ID |

---

## Snapshot 结构

```json
{
  "task_id": "tk-20260614-001",
  "created_at": "2026-06-14 12:00:00",

  "product": {
    "product_code": "XXX-001",
    "product_name_zh": "产品中文名",
    "product_report_version": 1
  },

  "ai": {
    "channel": "claude-code",
    "models": {
      "script_model": "claude-sonnet-4-20250514",
      "video_model": "kling-v1-5",
      "shot_grid_model": "claude-sonnet-4-20250514"
    },
    "parameters": {
      "temperature": 0.7,
      "max_tokens": 8192
    }
  },

  "video": {
    "mode": "single",
    "video_count": 1,
    "output_format": "mp4",
    "resolution": "1080x1920",
    "target_platform": "tiktok"
  },

  "script": {
    "language": "zh-CN",
    "tone": "轻松口语化",
    "duration_range": {
      "min_seconds": 15,
      "max_seconds": 60
    },
    "shot_grid_layout": "3x3",
    "formula": "AIDA"
  },

  "target": {
    "country": "日本",
    "language": "ja",
    "currency": "JPY"
  },

  "references": {
    "product_wiki_path": "wiki/产品库/产品档案/产品中文名.md",
    "report_wiki_path": "wiki/产品库/产品报告/产品中文名-产品报告-v1.md"
  },

  "recovery": {
    "max_retries": 3,
    "continue_from_fragment": true,
    "timeout_minutes": 30
  }
}
```

---

## 字段详解

### 1. 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `task_id` | `str` | 是 | 全局唯一任务标识，格式 `tk-{YYYYMMDD}-{序号}` |
| `created_at` | `str` | 是 | 任务创建时间 `yyyy-MM-dd HH:mm:ss` |
| `product` | `object` | 是 | 关联的产品信息 |
| `ai` | `object` | 是 | AI 模型和参数配置 |
| `video` | `object` | 是 | 视频输出配置 |
| `script` | `object` | 是 | 脚本生成配置 |
| `target` | `object` | 是 | 目标市场配置 |
| `references` | `object` | 是 | 关联的知识库文件路径 |
| `recovery` | `object` | 是 | 容错恢复策略 |

### 2. product

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `product_code` | `str` | 是 | 产品唯一编码 |
| `product_name_zh` | `str` | 是 | 产品中文名（用于定位 wiki 文件） |
| `product_report_version` | `int` | 是 | 使用的产品报告版本号 |

### 3. ai

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `channel` | `str` | 是 | — | AI CLI 渠道：`claude-code` / `codex` / `gemini` |
| `models.script_model` | `str` | 是 | — | 脚本生成的模型 ID |
| `models.video_model` | `str` | 是 | — | 视频生成的模型 ID |
| `models.shot_grid_model` | `str` | 否 | `script_model` 的值 | 分镜宫格图使用的模型 |
| `parameters.temperature` | `float` | 否 | `0.7` | 模型温度 |
| `parameters.max_tokens` | `int` | 否 | `8192` | 最大输出 token |

### 4. video

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `mode` | `str` | 是 | — | 视频模式：`single`(单视频) / `ab_test`(多版本对比) |
| `video_count` | `int` | 是 | — | 生成视频数量 |
| `output_format` | `str` | 否 | `mp4` | 输出格式 |
| `resolution` | `str` | 否 | `1080x1920` | 视频分辨率（竖屏默认 9:16） |
| `target_platform` | `str` | 是 | — | 目标平台：`tiktok` / `shopee` / `amazon` |

### 5. script

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `language` | `str` | 是 | — | 脚本语言代码（ISO 639-1） |
| `tone` | `str` | 否 | `自然口语化` | 脚本语调风格 |
| `duration_range.min_seconds` | `int` | 否 | `15` | 最小时长（秒） |
| `duration_range.max_seconds` | `int` | 否 | `60` | 最大时长（秒） |
| `shot_grid_layout` | `str` | 是 | — | 宫格图布局：`2x2` / `3x3` / `2x4` |
| `formula` | `str` | 否 | `AIDA` | 脚本公式：`AIDA` / `PAS` / `痛点-解决` / `before-after` |

### 6. target

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `country` | `str` | 是 | 目标国家（简体中文） |
| `language` | `str` | 是 | 目标语言代码 |
| `currency` | `str` | 否 | 货币代码 |

### 7. references

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `product_wiki_path` | `str` | 是 | 产品档案 wiki 路径 |
| `report_wiki_path` | `str` | 是 | 产品报告 wiki 路径 |

### 8. recovery

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `max_retries` | `int` | 否 | `3` | 每个片段最大重试次数 |
| `continue_from_fragment` | `bool` | 否 | `true` | 失败恢复时是否从断点续传 |
| `timeout_minutes` | `int` | 否 | `30` | 单个 AI CLI 调用超时时间 |

---

## 校验规则

1. `task_id` 必须在系统内唯一
2. `product.product_code` 必须能匹配到已存在的产品
3. `ai.channel` 必须是支持的渠道之一
4. `shot_grid_layout` 必须是有效布局格式
5. `duration_range.max_seconds` > `duration_range.min_seconds`
6. `references` 中的路径必须在创建时验证文件存在
7. 所有价格字段使用字符串，不包含货币符号

---

## 任务记录模板

任务创建时，根据 config_snapshot 生成如下任务记录：

```markdown
---
title: "任务 {task_id}"
type: "task"
tags: ["task", "{product_code}"]
created: {created_at}
task_id: "{task_id}"
status: "PENDING"
---

# 任务 {task_id}

## 基本信息
| 字段 | 值 |
|------|-----|
| 任务 ID | {task_id} |
| 产品 | [[{product_wiki_path}\|{product_name_zh}]] |
| 报告版本 | [[{report_wiki_path}\|v{product_report_version}]] |
| 创建时间 | {created_at} |
| 状态 | PENDING |

## 配置快照
<!-- 以下内容由系统自动生成，请勿手动修改 -->
```json
{完整的 config_snapshot JSON}
```

## 产物索引
| 类型 | 路径 | 状态 |
|------|------|------|
| 脚本 | - | 待生成 |
| 视频 | - | 待生成 |

## 执行时间线
| 时间 | 事件 |
|------|------|
| {created_at} | 任务创建 |
```

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-14 | v1.0 | 初始版本：完整 config_snapshot 结构定义 |

---

*此规范确保所有部署主机上的任务结构一致，恢复时可精准复现。*
