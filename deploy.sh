#!/usr/bin/env bash
# ============================================================================
# OPCAgent Vault — 一键部署脚本
# 用法: curl -sSL https://raw.githubusercontent.com/UnicaLiu/OPCAgent-Vault/main/deploy.sh | bash
# 或:   bash deploy.sh [安装路径]
# ============================================================================
set -euo pipefail

# --- 配置 ---
REPO_URL="git@github.com:UnicaLiu/OPCAgent-Vault.git"
DEFAULT_INSTALL_PATH="$HOME/OPCAgent-Vault"
INSTALL_PATH="${1:-$DEFAULT_INSTALL_PATH}"
BRANCH="main"

# --- 颜色 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

echo ""
echo -e "${BOLD}${BLUE}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${BLUE}║         OPCAgent Vault — 一键部署脚本 v1.0              ║${NC}"
echo -e "${BOLD}${BLUE}║         电商量化跑品知识库 · 本地化部署                  ║${NC}"
echo -e "${BOLD}${BLUE}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""

# --- 步骤 1: 检查依赖 ---
echo -e "${BOLD}[1/5]${NC} 检查依赖..."

check_command() {
    if ! command -v "$1" &>/dev/null; then
        echo -e "  ${RED}✗${NC} $1 未安装"
        return 1
    else
        echo -e "  ${GREEN}✓${NC} $1 ($(command -v "$1"))"
        return 0
    fi
}

DEPS_OK=true
check_command "git" || DEPS_OK=false
check_command "python3" || DEPS_OK=false

if [ "$DEPS_OK" = false ]; then
    echo ""
    echo -e "${RED}缺少必要的依赖。请先安装:${NC}"
    echo "  macOS:  brew install git python3"
    echo "  Ubuntu: sudo apt install git python3"
    exit 1
fi

# --- 步骤 2: 克隆仓库 ---
echo ""
echo -e "${BOLD}[2/5]${NC} 克隆 OPCAgent Vault..."

if [ -d "$INSTALL_PATH" ]; then
    echo -e "  ${YELLOW}⚠${NC}  目录已存在: ${INSTALL_PATH}"
    echo -e "  ${YELLOW}⚠${NC}  正在更新..."
    cd "$INSTALL_PATH"
    git pull origin "$BRANCH" 2>/dev/null || {
        echo -e "  ${RED}✗${NC} 更新失败，目录可能不是 git 仓库"
        echo "  请手动处理: rm -rf '$INSTALL_PATH' 然后重新运行"
        exit 1
    }
    echo -e "  ${GREEN}✓${NC} 已更新到最新版本"
else
    git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$INSTALL_PATH" 2>&1 | sed 's/^/  /'
    echo -e "  ${GREEN}✓${NC} 克隆完成 → ${INSTALL_PATH}"
fi

# --- 步骤 3: 创建主机独立目录 ---
echo ""
echo -e "${BOLD}[3/5]${NC} 初始化主机目录..."

cd "$INSTALL_PATH"

# 确保必要的 .gitkeep 文件存在
for dir in \
    raw/产品原始资料 raw/竞品参考 raw/爆品素材 raw/外部知识 \
    wiki/产品库/产品档案 wiki/产品库/产品报告 \
    wiki/任务中心/任务记录 wiki/任务中心/脚本库 \
    wiki/数据归因/归因报告 wiki/数据归因/数据洞察 \
    wiki/爆品分析/分析报告 wiki/爆品分析/素材索引; do
    mkdir -p "$dir"
    if [ ! -f "$dir/.gitkeep" ] && [ -z "$(ls -A "$dir" 2>/dev/null)" ]; then
        touch "$dir/.gitkeep"
    fi
done

echo -e "  ${GREEN}✓${NC} 目录结构就绪"

# --- 步骤 4: 验证 MCP Server ---
echo ""
echo -e "${BOLD}[4/5]${NC} 验证 MCP Server..."

if [ -f ".agents/servers/obsidian-vault/server.py" ]; then
    echo -e "  ${GREEN}✓${NC} MCP Server 已就绪"
else
    echo -e "  ${YELLOW}⚠${NC}  MCP Server 未找到（.agents/servers/obsidian-vault/server.py）"
    echo "  请确保 MCP Server 已正确安装"
fi

# --- 步骤 5: 完成 ---
echo ""
echo -e "${BOLD}[5/5]${NC} 部署完成！"
echo ""

# 计算文件统计
WIKI_COUNT=$(find wiki/ -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
RAW_COUNT=$(find raw/ -name "*.json" -o -name "*.md" 2>/dev/null | wc -l | tr -d ' ')

echo -e "${BOLD}${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}${GREEN}║                    部署成功！                           ║${NC}"
echo -e "${BOLD}${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}安装路径:${NC} ${INSTALL_PATH}"
echo -e "  ${BOLD}Wiki 页面:${NC} ${WIKI_COUNT}"
echo -e "  ${BOLD}Raw 文件:${NC}  ${RAW_COUNT}"
echo ""

echo -e "${BOLD}${YELLOW}下一步:${NC}"
echo ""
echo -e "  ${BLUE}1.${NC} 用 Obsidian 打开此目录作为 Vault:"
echo -e "     ${BOLD}open '${INSTALL_PATH}' -a Obsidian${NC}"
echo ""
echo -e "  ${BLUE}2.${NC} 配置 OPCAgent 后端指向此 Vault:"
echo "     修改 OPCAgent 项目中的配置文件，将 knowledge 路径设为:"
echo -e "     ${BOLD}${INSTALL_PATH}${NC}"
echo ""
echo -e "  ${BLUE}3.${NC} 投放第一个产品:"
echo -e "     将产品 JSON 放入 ${BOLD}raw/产品原始资料/${NC}"
echo -e "     或通过 Web 页面 (端口 8766) 录入"
echo ""
echo -e "  ${BLUE}4.${NC} 阅读知识库指南:"
echo -e "     - 行为规则:   ${BOLD}CLAUDE.md${NC}"
echo -e "     - 中央导航:   ${BOLD}wiki/index.md${NC}"
echo -e "     - 摄入标准:   ${BOLD}wiki/公共专家库/工具指南/知识库摄入标准.md${NC}"
echo -e "     - 开发指南:   ${BOLD}wiki/公共专家库/工具指南/Web开发-知识库集成指南.md${NC}"
echo ""

echo -e "${BOLD}${GREEN}知识库飞轮已就绪，开始投放产品吧！ 🚀${NC}"
echo ""
