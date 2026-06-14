# OPCAgent Vault — 电商量化跑品知识库

[![Vault Version](https://img.shields.io/badge/vault-v1.0-blue)](https://github.com/UnicaLiu/opcagent-vault)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

> **AI 驱动的电商量化短视频营销系统知识库。一键部署到任意本地主机。**

基于 **Karpathy LLM-Wiki 三层架构** + **Skillify 渐进式披露** 理念构建。以「产品」为唯一业务源头，串联完整量化链路：

```
产品原始资料 → 公共专家知识 → 产品分析报告 → 爆品视频分析 → 任务执行 → 数据归因反馈
     ↑                                                              │
     └──────────────── 归因结果反哺产品认知 ───────────────────────────┘
```

---

## 🚀 一键部署

```bash
curl -sSL https://raw.githubusercontent.com/UnicaLiu/opcagent-vault/main/deploy.sh | bash
```

或手动：

```bash
git clone git@github.com:UnicaLiu/opcagent-vault.git ~/OPCAgent-Vault
cd ~/OPCAgent-Vault
```

然后用 Obsidian 打开 `~/OPCAgent-Vault` 作为 Vault。

---

## 📁 结构

```
OPCAgent Vault/
├── README.md                     ← 本文件
├── CLAUDE.md                     ← Agent 行为规则
├── AGENTS.md                     ← 子代理定义 + 注册表
├── deploy.sh                     ← 一键部署脚本
├── raw/                          ← 原始资料层（主机独立）
│   ├── 产品原始资料/              ← 产品 JSON + 图片
│   ├── 竞品参考/
│   ├── 爆品素材/
│   └── 外部知识/
├── wiki/                         ← 知识库层
│   ├── index.md                  ← 中央导航
│   ├── 公共专家库/               ← 共享知识（Git 同步）
│   │   ├── 平台规则/
│   │   ├── 投放策略/
│   │   ├── 内容方法论/
│   │   └── 工具指南/             ← System Prompt / Task 规范 / 摄入标准 / 开发指南
│   ├── 产品库/                   ← 主机独立
│   ├── 爆品分析/                 ← 主机独立
│   ├── 任务中心/                 ← 主机独立
│   ├── 数据归因/                 ← 主机独立
│   └── 对比分析/                 ← 主机独立
└── 知识库基础搭建原理/           ← 理论参考
```

---

## 🔧 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    OPCAgent 系统                          │
│                                                          │
│  Web Agent 页面 (8766-8773)  →  FastAPI 后端             │
│         │                           │                    │
│         │                           ├→ raw/ 写 JSON      │
│         │                           ├→ json_to_md 工具   │
│         │                           └→ Claude CLI 子进程  │
│         │                                │               │
│         └────────────────────────────────┤               │
│                                          │               │
│  ┌───────────────────────────────────────┼───────────┐  │
│  │                    OPCAgent Vault     │           │  │
│  │                                       ▼           │  │
│  │  .claude/mcp.json → MCP Server ← Claude CLI       │  │
│  │       │                    │                      │  │
│  │       ▼                    ▼                      │  │
│  │   raw/ (只读)    →    wiki/ (Agent 维护)          │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 📦 部署后初始化

```bash
# 1. 克隆
git clone git@github.com:UnicaLiu/opcagent-vault.git ~/OPCAgent-Vault

# 2. 用 Obsidian 打开此目录

# 3. 配置 OPCAgent 后端指向此 Vault
#    修改 app/module/product_info/config.json:
#    "knowledge_link": "/Users/你的用户名/OPCAgent-Vault"

# 4. 投放第一个产品
#    将产品 JSON 放入 raw/产品原始资料/
#    或通过 Web 页面录入

# 5. 启动 OPCAgent
#    cd /path/to/OPCAgent
#    uvicorn app.main:app --reload
```

---

## 🔄 多主机同步

| 内容 | 同步方式 |
|------|---------|
| Vault 结构 + 配置 | `git pull` |
| `wiki/公共专家库/` | `git pull`（核心团队维护） |
| 产品/任务/归因数据 | 主机独立，不同步 |
| `raw/` 产品资料 | 主机独立 |

---

## 📖 关键文件

| 文件 | 说明 |
|------|------|
| [[CLAUDE]] | Vault 行为配置（每次 AI 启动必读） |
| [[AGENTS]] | 8 个子代理 + 10 个 Agent 页面注册表 |
| [[wiki/index]] | 中央导航 + 知识库统计 |
| [[System-Prompt-模板库]] | 5 个 Agent 的 System Prompt（版本化） |
| [[Task-Config-Snapshot-规范]] | 任务冻结参数完整定义 |
| [[知识库摄入标准]] | 两条摄入路径说明 |
| [[Web开发-知识库集成指南]] | Web 开发者集成手册 |

---

*基于 Andrej Karpathy LLM-Wiki 模式 + Skillify 渐进式披露理念。*
*关联项目：OPCAgent*
