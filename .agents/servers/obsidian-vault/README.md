# Obsidian Vault MCP Server

将 Obsidian 知识库的 wiki/ 操作暴露为 MCP 工具，供 Claude Code、Codex 等 AI 工具调用。

## 核心功能

| 工具 | 说明 |
|------|------|
| `wiki_stats` | 获取当前统计 |
| `wiki_search` | 全文搜索 |
| `wiki_get_log` | 查看操作日志 |
| `wiki_lint` | 全库健康检查 |
| `wiki_read_page` | 读取文件 |
| `wiki_list_raw` | 列出 raw/ 文件 |
| `wiki_create_page` | 创建页面 (自动维护 index + log) |
| `wiki_update_page` | 更新页面 (自动备份) |
| `wiki_delete_page` | 安全删除 (入链检查 + 备份) |
| `wiki_ingest` | ★ 完整摄入管道 (一步完成 5 步操作) |
| `wiki_rebuild_index` | 重建 index.md |

## 使用方式

### MCP 模式 (Claude Code / Codex)

配置 `.claude/mcp.json` 或 `.codex/mcp.json`：

```json
{
  "mcpServers": {
    "obsidian-vault": {
      "command": "python3",
      "args": [
        ".agents/servers/obsidian-vault/server.py"
      ],
      "env": {
        "OBSIDIAN_VAULT_PATH": "/Users/Zhuanz/Documents/Obsidian Vault"
      }
    }
  }
}
```

### CLI 模式 (手动 / 脚本)

```bash
# 统计
python3 server.py --cli stats

# 搜索
python3 server.py --cli search "内容判断力"

# 健康检查
python3 server.py --cli lint

# 摄入 raw 文件
python3 server.py --cli ingest "钟老师聊TK/76344851.md" \
  --title "TikTok 内容判断力训练" \
  --summary "三步训练法：看→对比→反推" \
  --tags Tiktok 内容判断力 钟老师

# 创建概念页
python3 server.py --cli create-page concept "新概念" \
  --content "详细的 Markdown 正文" \
  --tags tag1 tag2 \
  --sources "wiki/来源/xxx" "wiki/来源/yyy"
```

## 环境变量

- `OBSIDIAN_VAULT_PATH` — vault 根目录 (默认: 当前工作目录)

## 设计原则

- **唯一写入网关**: 所有 wiki/ 变更都经过此 server
- **原子操作**: 创建/更新/删除都是完整文件写入
- **自动维护**: index.md 和 log.md 自动更新，不可能遗漏
- **Schema 硬约束**: ≥2 来源才创建概念/实体 (Karpathy 自下而上原则)
- **安全删除**: 入链检查 + 备份，禁止误删被引用的页面
- **无外部依赖**: 纯 Python 3.9+ 标准库 + 手写 MCP 协议
