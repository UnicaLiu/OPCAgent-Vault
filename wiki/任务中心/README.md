---
title: "任务中心"
type: "hub"
tags: ["任务中心", "导航"]
created: 2026-06-14
---

# 任务中心

> OPCAgent 的任务执行记录和生成的脚本归档。
> 每个任务冻结完整的 config_snapshot，确保历史可复现。

---

## 任务记录 `任务记录/`

每个任务文件以 `task-{task_id}.md` 命名，包含：

| 字段 | 说明 |
|------|------|
| task_id | 全局唯一任务标识 |
| 关联产品 | 产品 wiki 链接 |
| 报告版本 | 使用的产品报告版本号 |
| config_snapshot | 冻结的任务参数（完整 JSON） |
| 状态 | PENDING → RUNNING_SCRIPT → RUNNING_VIDEO → SUCCESS / FAILED |
| 产物索引 | 生成的脚本、视频路径 |
| 时间线 | 创建时间 / 开始时间 / 完成时间 |
| 失败信息 | failure_reason + 错误节点 + 堆栈 |

### 任务状态机

```
PENDING → RUNNING_SCRIPT → RUNNING_VIDEO → SUCCESS
              ↓                    ↓
            FAILED              FAILED
```

## 脚本库 `脚本库/`

生成的脚本文件，包含：

| 字段 | 说明 |
|------|------|
| 脚本文本 | 完整视频脚本（旁白 + 画面描述） |
| 分镜宫格图 | 引用分镜图文件路径 |
| 单个分镜图 | 每个分镜的独立截图引用 |
| prompt_snapshot | 生成脚本时的 AI prompt |
| 关联任务 | 所属 task_id |

---

## 当前任务列表

<!-- Agent 自动维护 -->

| 任务 ID | 产品 | 状态 | 创建时间 |
|---------|------|------|---------|
| *(等待第一个任务)* | - | - | - |

---

*任务中心是 OPCAgent 的执行日志——记录每一次"跑品"的完整轨迹。*
