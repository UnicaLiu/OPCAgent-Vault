---
title: "Web 开发：知识库使用与摄入集成指南"
type: "tool"
tags: ["Web开发", "集成", "MCP", "CLI", "FastAPI", "Agent"]
created: 2026-06-14
version: "1.0"
status: "active"
---

# Web 开发：知识库使用与摄入集成指南

> 面向 OPCAgent Web 页面开发者。本文档定义 Web 页面如何与 Claude CLI、MCP Server、知识库 Vault 三者协作，
> 完成从"用户输入"到"知识沉淀"的完整链路。

---

## 一、架构全景

```
┌──────────────────────────────────────────────────────────────────────┐
│                         OPCAgent 系统架构                              │
│                                                                       │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────────────┐  │
│  │   Web 页面    │────▶│  FastAPI 后端 │────▶│  raw/ 产品原始资料/   │  │
│  │  (浏览器)     │     │  (Python)    │     │  {productCode}.json  │  │
│  └──────────────┘     └──────┬───────┘     └──────────┬───────────┘  │
│                              │                         │              │
│                              │ ① 写 JSON 到 raw/       │              │
│                              │ ② 调 json_to_md 生成事实 MD            │
│                              │                         │              │
│                              ▼                         ▼              │
│                    ┌──────────────────┐    ┌──────────────────────┐   │
│                    │  Claude CLI 子进程 │───▶│  OPCAgent Vault      │   │
│                    │  claude -p --bare │    │  (Obsidian 知识库)   │   │
│                    └────────┬─────────┘    │                      │   │
│                             │              │  raw/   ← 原始资料    │   │
│                             │ MCP          │  wiki/  ← 结构化知识  │   │
│                             ▼              └──────────────────────┘   │
│                    ┌──────────────────┐                               │
│                    │   MCP Server     │                               │
│                    │   server.py      │                               │
│                    │   (JSON-RPC)     │                               │
│                    └──────────────────┘                               │
└──────────────────────────────────────────────────────────────────────┘
```

**数据流向**：

```
用户输入 → Web 页面 → FastAPI 后端
                         │
                         ├──→ ① raw/ 写 JSON（产品基础事实）
                         ├──→ ② json_to_md 生成 MD（产品基础事实 MD）
                         ├──→ ③ 启动 Claude CLI 子进程
                         │       ├── 读取 @CLAUDE.md（行为规则）
                         │       ├── 读取 raw/ JSON（产品数据）
                         │       ├── 读取 @System-Prompt（任务指令）
                         │       └── 调用 MCP → 写入 wiki/
                         │
                         └──→ ④ WebSocket 推送实时进度
```

---

## 二、以"产品信息录入"为例的完整链路

> 这是最核心的场景。理解这个，其他功能（任务、脚本、归因）都是同一模式的变体。

### 第 1 步：用户在 Web 页面填写产品信息

Web 表单字段（对应 `parameter-io-standard.md`）：

```
产品编码: SHG-001
产品中文名: 智能桌面种植机
目标国家: 日本
类目: 家居 / 智能设备 / 园艺
卖点1: 全自动托管，忘了浇水也不怕
卖点2: 6倍生长速度，看得见的成长
...
价格: 299 → 促销 249
SKU: 3孔/6孔 × 3色 = 6个 SKU
```

### 第 2 步：FastAPI 后端处理 — 生成基础事实文件

```python
# app/web/product_entry.py — 产品信息录入后端

import json
import subprocess
import os
from pathlib import Path

VAULT_PATH = Path("/Users/Zhuanz/Developer/OPCAgent/knowledge/OPCAgent Vault")
RAW_PRODUCT_DIR = VAULT_PATH / "raw" / "产品原始资料"

def handle_product_submit(form_data: dict) -> dict:
    """处理产品信息录入提交"""

    # ============================================
    # 阶段 1：生成产品基础事实 JSON
    # ============================================
    product_code = form_data["productCode"]
    json_path = RAW_PRODUCT_DIR / f"{product_code}.json"

    product_json = build_product_json(form_data)  # 按 parameter-io-standard 格式
    json_path.write_text(
        json.dumps(product_json, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    # ============================================
    # 阶段 2：生成产品基础事实 MD（产品档案）
    # ============================================
    # 使用 json_to_md 工具把 JSON 转为 Markdown
    # 这个 MD 是"事实层"——不含 AI 分析，只有产品基础数据
    subprocess.run([
        "python3",
        str(VAULT_PATH.parent.parent / "app" / "tools" / "json_to_md" / "json_to_md.py"),
        str(json_path),
        "-o", str(VAULT_PATH / "wiki" / "产品库" / "产品档案")
    ], check=True)

    # ============================================
    # 阶段 3：启动 Claude CLI 生成产品报告
    # ============================================
    report_result = generate_product_report(
        product_code=product_code,
        product_name_zh=form_data["productNameZh"]
    )

    return {
        "status": "success",
        "product_code": product_code,
        "fact_md": f"wiki/产品库/产品档案/{form_data['productNameZh']}.md",
        "report_md": report_result["path"],
        "report_version": report_result["version"]
    }
```

### 第 3 步：Claude CLI 子进程 — 生成动态产品报告

```python
def generate_product_report(product_code: str, product_name_zh: str) -> dict:
    """启动 Claude CLI 子进程，生成产品分析报告"""

    # Claude CLI 的工作目录必须是 Vault 根目录
    # 这样 @file 引用和 MCP 路径才能正确解析

    # Claude 的 System Prompt 通过 --system-prompt 或 @file 传入
    # 使用 @file 引用 Vault 中的 prompt 模板（遵守 AI CLI 规范）
    prompt = f"""
读取 @CLAUDE.md 了解知识库规则。

然后执行以下任务：

1. 读取产品基础事实：
   @raw/产品原始资料/{product_code}.json

2. 读取已有的产品档案（如果存在）：
   @wiki/产品库/产品档案/{product_name_zh}.md

3. 读取专家知识：
   去 wiki/公共专家库/ 中找到与目标市场、产品类目相关的平台规则和内容方法论。

4. 生成版本化产品报告：
   - 确定版本号（已有报告取最大序号+1，没有则用 1）
   - 通过 MCP wiki_create_page 写入 wiki/产品库/产品报告/{product_name_zh}-产品报告-v{{N}}.md
   - 报告需包含：市场定位、目标受众画像、卖点优先级排序、内容策略建议、禁忌与风险提示
   - 新报告 is_active: true，旧版本标记 inactive
   - 使用 [[wikilinks]] 建立与专家知识页面的关联

5. 更新产品档案的 report_versions 字段（通过 MCP wiki_update_page）

6. 完成后，输出 JSON 格式的结果：{{"version": N, "path": "wiki/产品库/产品报告/...md"}}
"""

    result = subprocess.run(
        [
            "claude",
            "-p", "--bare",           # 非交互模式，只输出结果
            "--model", "claude-sonnet-4-20250514",
            "--max-tokens", "8192",
            "--working-dir", str(VAULT_PATH),
            prompt
        ],
        capture_output=True,
        text=True,
        timeout=300,                  # 5 分钟超时
        cwd=str(VAULT_PATH)           # 工作目录 = Vault 根
    )

    # 解析 Claude 的最后一行输出（JSON 结果）
    output_lines = result.stdout.strip().split("\n")
    return json.loads(output_lines[-1])
```

### 第 4 步：MCP Server 自动处理

Claude 在子进程中调用 MCP 工具时，MCP Server 自动完成：

```
MCP wiki_create_page("product_report", "智能桌面种植机-产品报告-v1", content, ...)
    │
    ├── ✅ 创建 wiki/产品库/产品报告/智能桌面种植机-产品报告-v1.md
    ├── ✅ 自动生成 frontmatter（title/type/tags/created/status）
    ├── ✅ 更新 wiki/index.md 统计表
    └── ✅ 追加日志到 wiki/log.md（如果存在）
```

---

## 三、Vault 路径速查（开发者用）

### 3.1 写入路径

| 内容 | 写入方式 | 路径模板 |
|------|---------|---------|
| 产品基础事实 JSON | FastAPI 直接写 | `raw/产品原始资料/{productCode}.json` |
| 产品基础事实 MD | json_to_md 工具 | `wiki/产品库/产品档案/{productNameZh}.md` |
| 产品动态报告 MD | Claude CLI → MCP | `wiki/产品库/产品报告/{productNameZh}-产品报告-v{N}.md` |
| 任务记录 MD | Claude CLI → MCP | `wiki/任务中心/任务记录/task-{task_id}.md` |
| 脚本 MD | Claude CLI → MCP | `wiki/任务中心/脚本库/{产品名}-脚本-v{N}.md` |
| 爆品分析 MD | Claude CLI → MCP | `wiki/爆品分析/分析报告/{主题}-分析报告-{日期}.md` |
| 归因报告 MD | Claude CLI → MCP | `wiki/数据归因/归因报告/{产品名}-归因报告-{日期}.md` |
| 数据洞察 MD | Claude CLI → MCP | `wiki/数据归因/数据洞察/{主题}-洞察-{日期}.md` |
| System Prompt | 人类直接编辑 | `wiki/公共专家库/工具指南/System-Prompt-模板库.md` |

### 3.2 读取路径（Agent 用）

| 知识 | 路径 | 说明 |
|------|------|------|
| 行为规则 | `CLAUDE.md` | 每次启动必读 |
| 知识库全貌 | `wiki/index.md` | 了解当前有哪些内容 |
| 公共专家知识 | `wiki/公共专家库/` | 平台规则、策略、方法论 |
| 产品档案 | `wiki/产品库/产品档案/{产品名}.md` | 产品基础事实 |
| 产品报告 | `wiki/产品库/产品报告/{产品名}-产品报告-v{N}.md` | AI 分析报告 |
| 任务 config_snapshot | `wiki/任务中心/任务记录/task-{id}.md` | 任务冻结参数 |

---

## 四、MCP Server 集成

### 4.1 MCP Server 位置和启动

```
Vault 内部: .agents/servers/obsidian-vault/server.py
连接方式:   JSON-RPC 2.0 over stdio
配置:       .claude/mcp.json
```

Claude CLI 通过 `.claude/mcp.json` 自动发现并连接 MCP Server。
**Web 后端不需要直接调 MCP**——MCP 是给 Claude CLI 子进程用的。
Web 后端只负责：写 raw/ 文件、调 json_to_md、启动 CLI 子进程。

### 4.2 MCP 工具清单（供 System Prompt 中引用）

| 工具 | 参数 | 用途 |
|------|------|------|
| `wiki_stats` | 无 | 获取知识库统计 |
| `wiki_search` | `query` | 全文搜索 |
| `wiki_read_page` | `path` | 读取文件 |
| `wiki_create_page` | `type, title, content, tags, sources` | 创建页面 |
| `wiki_update_page` | `path, content` | 更新页面 |
| `wiki_delete_page` | `path, force` | 安全删除 |
| `wiki_ingest` | `raw_path, title, summary, tags, entities, concepts` | 从 raw/ 摄入 |
| `wiki_lint` | 无 | 健康检查 |
| `wiki_list_raw` | `pattern` | 列出 raw/ 文件 |

### 4.3 在 System Prompt 中指导 Claude 使用 MCP

```markdown
## 写入知识库

当你需要创建或更新 wiki 页面时，使用 MCP 工具：

- 新建页面：wiki_create_page(type="product_report", title="...", content="...", tags=[...])
- 更新页面：wiki_update_page(path="wiki/...", content="...")
- 读取页面：wiki_read_page(path="wiki/...")

不要直接使用 Write/Edit 工具操作 wiki/ 下的文件。
```

---

## 五、Claude CLI 集成规范

### 5.1 调用方式

```bash
claude -p --bare \
  --model "claude-sonnet-4-20250514" \
  --max-tokens "8192" \
  --working-dir "/path/to/OPCAgent Vault" \
  "任务描述"
```

| 参数 | 说明 |
|------|------|
| `-p` | 非交互模式（pipe mode） |
| `--bare` | 只输出结果，不输出对话过程 |
| `--model` | 模型 ID |
| `--max-tokens` | 最大输出 token |
| `--working-dir` | 工作目录 = Vault 根（确保 @file 和 MCP 路径正确） |

### 5.2 System Prompt 传入方式

**方案一（推荐）：@file 引用 Vault 中的模板**

```python
prompt = f"""
你的角色和任务定义在 @wiki/公共专家库/工具指南/System-Prompt-模板库.md 的「产品报告生成」章节。

请按该模板的要求执行任务。产品编码：{product_code}
"""
```

**方案二：--system-prompt 参数**

```bash
claude -p --bare --system-prompt "$(cat system_prompt.txt)" "任务描述"
```

> 遵循 AI CLI 规范：**必须使用 CLI 自带的 @file 功能关联文件，不允许把文件路径、MD 内容直接拼进 prompt。**

### 5.3 子进程管理

```python
import subprocess
import threading
import redis

def run_claude_task(prompt: str, task_id: str, redis_client: redis.Redis):
    """在 Celery task 中运行 Claude CLI，实时推送进度"""

    log_key = f"task:logs:{task_id}"
    progress_key = f"task:progress:{task_id}"

    proc = subprocess.Popen(
        ["claude", "-p", "--bare",
         "--model", "claude-sonnet-4-20250514",
         "--max-tokens", "8192",
         "--working-dir", str(VAULT_PATH),
         prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=str(VAULT_PATH)
    )

    # 逐行读取 stdout → 净化 → Redis List → WebSocket 推送前端
    for line in proc.stdout:
        clean_line = sanitize_output(line)  # 去掉 ANSI 颜色码等
        redis_client.rpush(log_key, clean_line)
        redis_client.ltrim(log_key, -1000, -1)  # 保留最近 1000 行

    proc.wait(timeout=300)

    if proc.returncode != 0:
        redis_client.hset(progress_key, "status", "FAILED")
        raise RuntimeError(f"Claude CLI exited with {proc.returncode}")

    redis_client.hset(progress_key, "status", "SUCCESS")
```

### 5.4 System Prompt 编写原则

基于你的架构模式，System Prompt 应该：

| 原则 | 错误示例 | 正确示例 |
|------|---------|---------|
| **告诉它去哪儿找，别替它读** | "产品信息如下：{整个JSON内容}" | "读取 @raw/产品原始资料/{code}.json" |
| **给指令，不给数据** | 把 wiki 页面内容全粘进 prompt | "去 wiki/公共专家库/平台规则/ 找日本市场规则" |
| **明确输出格式** | "写一份报告" | "写入 wiki/产品库/产品报告/{name}-产品报告-v{N}.md，frontmatter type=product_report" |
| **指定工具** | "创建文件" | "使用 MCP wiki_create_page 创建" |

---

## 六、各功能模块的开发 Recipe

### 6.1 产品信息录入 + 报告生成

```
Web 页面: 产品管理 (端口 8766)

完整链路:
  用户填表 → 提交
    │
    ├── 1. FastAPI 构建 product JSON → 写 raw/产品原始资料/{code}.json
    ├── 2. 调 json_to_md → 生成 wiki/产品库/产品档案/{name}.md
    ├── 3. WebSocket 推送: "基础事实已生成，正在生成分析报告..."
    ├── 4. 启动 Claude CLI:
    │      prompt = "@wiki/公共专家库/工具指南/System-Prompt-模板库.md 产品报告生成章节
    │                 productCode={code}"
    │      Claude 自己:
    │        → 读 raw/ JSON → 获取产品数据
    │        → 读 wiki/公共专家库/ → 获取市场知识
    │        → MCP wiki_create_page → 写入报告
    │        → MCP wiki_update_page → 更新产品档案 report_versions
    ├── 5. WebSocket 推送: "报告生成完成"
    └── 6. 前端刷新 → 显示报告链接
```

### 6.2 任务创建 + 脚本生成

```
Web 页面: 任务控制 (端口 8771)

完整链路:
  用户选择产品 + 报告版本 + 配置参数 → 提交
    │
    ├── 1. FastAPI 构建 config_snapshot（参照 Task-Config-Snapshot-规范）
    ├── 2. 启动 Claude CLI:
    │      prompt = "@wiki/公共专家库/工具指南/System-Prompt-模板库.md 脚本生成章节
    │                 task_id={id}"
    │      Claude 自己:
    │        → MCP wiki_create_page → 写入任务记录（含 config_snapshot）
    │        → 读产品报告 → 读内容方法论
    │        → 生成脚本 MD → MCP wiki_create_page → 写入脚本库
    │        → 生成 shot_grid_config
    ├── 3. WebSocket 推送进度
    └── 4. 前端显示脚本 + 分镜宫格图
```

### 6.3 爆品分析

```
Web 页面: 爆品分析 (端口 8768)

完整链路:
  用户上传爆款视频描述/截图 → 提交
    │
    ├── 1. FastAPI 写 raw/爆品素材/{日期}-{描述}.md（含视频链接、截图路径、互动数据）
    ├── 2. 启动 Claude CLI:
    │      prompt = "@wiki/公共专家库/工具指南/System-Prompt-模板库.md 爆品视频分析章节"
    │      Claude 自己:
    │        → 读 raw/爆品素材/ 中的文件
    │        → 分析视频结构、文案、视觉、音频
    │        → MCP wiki_create_page → 写入分析报告
    │        → 更新素材索引
    │        → 如有新打法 → 建议更新 wiki/公共专家库/内容方法论/
    └── 3. 前端显示分析报告
```

### 6.4 数据归因

```
Web 页面: 归因分析 (端口 8769)

完整链路:
  用户上传投放数据或关联广告账户 → 触发分析
    │
    ├── 1. FastAPI 拉取投放数据 → 写 raw/（暂定格式，待数据归因模块规范）
    ├── 2. 启动 Claude CLI:
    │      prompt = "@wiki/公共专家库/工具指南/System-Prompt-模板库.md 数据归因分析章节"
    │      Claude 自己:
    │        → 读 raw/ 数据
    │        → 关联对应产品和任务
    │        → MCP wiki_create_page → 写入归因报告
    │        → 提炼洞察 → MCP wiki_create_page → 写入数据洞察
    │        → 如有可反哺产品认知的结论 → 更新产品报告
    └── 3. 前端显示归因报告和洞察
```

---

## 七、文件格式规范速查

### 7.1 产品基础事实 JSON（raw/）

```json
{
  "productCode": "SHG-001",
  "productNameZh": "智能桌面种植机",
  "productNameLocal": "スマートハーブガーデン",
  "country": "日本",
  "categories": ["家居", "智能设备", "园艺"],
  "createdAt": "2026-06-14 12:00:00",
  "extendedAttributes": [
    { "name": "光照功率", "value": "24W 全光谱 LED" }
  ],
  "skus": [
    {
      "skuId": "SHG-3-W",
      "attributes": { "颜色": "奶油白", "孔位": "3孔" },
      "price": { "originalPrice": "249", "promotionalPrice": "199" }
    }
  ],
  "keySellingPoints": [
    {
      "title": "卖点标题",
      "description": "卖点详细描述"
    }
  ],
  "price": { "originalPrice": "299", "promotionalPrice": "249" }
}
```

> 完整字段定义见 `app/module/product_info/parameter-io-standard.md`

### 7.2 Wiki 页面 Frontmatter

```yaml
---
title: "页面标题"
type: "product | product_report | task | script | analysis | attribution | concept | tool | rule | comparison"
tags: ["标签1", "标签2"]
created: 2026-06-14
modified: 2026-06-14
status: "draft | active | archived"
sources: ["raw/xxx.md"]
---
```

### 7.3 任务 config_snapshot 结构

```json
{
  "task_id": "tk-20260614-001",
  "created_at": "2026-06-14 12:00:00",
  "product": {
    "product_code": "SHG-001",
    "product_name_zh": "智能桌面种植机",
    "product_report_version": 1
  },
  "ai": {
    "channel": "claude-code",
    "models": {
      "script_model": "claude-sonnet-4-20250514",
      "video_model": "kling-v1-5"
    }
  },
  "script": {
    "language": "ja",
    "duration_range": { "min_seconds": 15, "max_seconds": 60 },
    "shot_grid_layout": "3x3"
  },
  "target": {
    "country": "日本",
    "language": "ja"
  }
}
```

> 完整字段定义见 [[Task-Config-Snapshot-规范]]

---

## 八、WebSocket 实时推送规范

### 8.1 Redis 数据结构

```python
# 任务进度
redis_client.hset(f"task:progress:{task_id}", mapping={
    "status": "RUNNING_SCRIPT",
    "step": "生成分镜脚本",
    "progress": "45",
    "message": "正在分析产品卖点..."
})

# 滚动日志（前端实时展示）
redis_client.rpush(f"task:logs:{task_id}", "[14:32:01] 开始生成产品报告...")
redis_client.ltrim(f"task:logs:{task_id}", -1000, -1)  # 保留最近 1000 行
```

### 8.2 WebSocket 端点

```
WS /ws/tasks/{task_id}
```

前端连接此端点后，实时接收日志推送。

---

## 九、错误处理与恢复

### 9.1 Claude CLI 错误处理

```python
class ClaudeCLIError(Exception):
    def __init__(self, returncode, stderr, task_id):
        self.returncode = returncode
        self.stderr = stderr
        self.task_id = task_id

def run_claude_with_retry(prompt: str, task_id: str, max_retries: int = 3):
    for attempt in range(max_retries):
        try:
            return run_claude_task(prompt, task_id, redis_client)
        except ClaudeCLIError as e:
            if attempt == max_retries - 1:
                # 最后一次也失败了 → 记录死信
                record_dead_letter(task_id, e)
                raise
            # 重试前等待递增
            time.sleep(2 ** attempt)
```

### 9.2 产物验证

Claude CLI 完成后，Web 后端必须验证产物：

```python
def verify_artifact(expected_path: str) -> bool:
    full_path = VAULT_PATH / expected_path
    if not full_path.exists():
        return False
    if full_path.stat().st_size == 0:
        return False
    # 验证 frontmatter
    content = full_path.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return False
    return True
```

### 9.3 死信队列

```python
def record_dead_letter(task_id: str, error: Exception):
    """任务失败 3 次后写入死信队列"""
    dead_letter = {
        "task_id": task_id,
        "error": str(error),
        "timestamp": datetime.now().isoformat(),
        "node": "claude_cli",
        "stacktrace": traceback.format_exc()
    }
    # 写入 PostgreSQL failed_task_log 表
    # 或写入 Redis 死信队列
```

---

## 十、开发检查清单

新功能上线前，确认以下项：

| # | 检查项 |
|---|--------|
| 1 | raw/ JSON 格式符合 parameter-io-standard.md |
| 2 | System Prompt 引用了 @file 而非内联文件内容 |
| 3 | Claude CLI 工作目录设置为 Vault 根 |
| 4 | MCP wiki_create_page 调用的 type 参数正确 |
| 5 | 产物路径验证（文件存在 + 非空 + frontmatter 完整） |
| 6 | WebSocket 推送了进度更新 |
| 7 | 失败时有死信记录 |
| 8 | wiki/index.md 统计已更新（MCP 自动） |
| 9 | 前端能正确展示 wikilinks（Obsidian URI 或渲染为链接） |

---

## 十一、关键文件索引

| 文件 | 内容 |
|------|------|
| [[CLAUDE]] | Vault 行为规则 + 知识库结构 |
| [[AGENTS]] | 子代理定义 + Agent 页面注册表 |
| [[知识库摄入标准]] | 两条摄入路径（Git 同步 vs MCP 写入）的说明 |
| [[System-Prompt-模板库]] | 各 Agent 的 System Prompt 模板 |
| [[Task-Config-Snapshot-规范]] | config_snapshot 完整字段定义 |
| `app/module/product_info/parameter-io-standard.md` | 产品信息 JSON 输入输出规范 |
| `app/standard/knowledge-md-format-standard.md` | Markdown 文档格式规范 |
| `app/module/ai_cli/README.md` | AI CLI 调用规范（@file 原则） |

---

## 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-14 | v1.0 | 初始版本：完整 Web 开发集成指南 |
