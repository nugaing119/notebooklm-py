#!/bin/bash
# NotebookLM AntiGravity Skill — Quick Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/nugaing119/notebooklm-py/main/notebook-py/install.sh | bash

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  NotebookLM AntiGravity Skill Installer${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── 1. Install notebooklm-py ──
echo -e "${YELLOW}[1/3]${NC} Installing notebooklm-py..."
if command -v uv &> /dev/null; then
    uv tool install "notebooklm-py[browser]"
else
    pip install "notebooklm-py[browser]" --quiet
fi

# Install Playwright Chromium if needed
if ! python3 -c "from playwright.sync_api import sync_playwright" &> /dev/null 2>&1; then
    python3 -m playwright install chromium 2>/dev/null || true
fi
echo -e "${GREEN}  ✓ notebooklm-py installed${NC}"

# ── 2. Download Skill File ──
echo -e "${YELLOW}[2/3]${NC} Downloading AntiGravity skill..."
SKILL_DIR="$HOME/.antigravity/skills/notebooklm"
mkdir -p "$SKILL_DIR"
curl -fsSL \
  "https://raw.githubusercontent.com/nugaing119/notebooklm-py/main/notebook-py/NotebookLM_AntiGravity_Skill.md" \
  -o "$SKILL_DIR/SKILL.md"
echo -e "${GREEN}  ✓ Skill saved to: $SKILL_DIR/SKILL.md${NC}"

# Also download the pipeline script
SCRIPT_DIR="$HOME/.antigravity/skills/notebooklm/scripts"
mkdir -p "$SCRIPT_DIR"
curl -fsSL \
  "https://raw.githubusercontent.com/nugaing119/notebooklm-py/main/notebook-py/pipeline.py" \
  -o "$SCRIPT_DIR/pipeline.py" 2>/dev/null || true

# ── 3. Login ──
echo -e "${YELLOW}[3/3]${NC} Authenticating with NotebookLM..."
echo ""
echo -e "  A Chromium window will open. Sign in with your Google account."
echo -e "  Press ENTER in this terminal once you see the NotebookLM homepage."
echo ""
notebooklm login

echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✓ All done! Skill is ready to use.${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo "  Verify setup:"
echo "  $ notebooklm list"
echo ""
echo "  To run a Meeting Prep dashboard:"
echo "  $ python3 $SCRIPT_DIR/pipeline.py"
echo ""
