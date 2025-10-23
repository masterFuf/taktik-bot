#!/bin/bash
# Taktik Bot - Installation/Update Script (Linux/macOS)
# This script installs or updates Taktik Bot to the latest version

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Functions
print_success() { echo -e "${GREEN}$1${NC}"; }
print_info() { echo -e "${CYAN}$1${NC}"; }
print_warning() { echo -e "${YELLOW}$1${NC}"; }
print_error() { echo -e "${RED}$1${NC}"; }

# Parse arguments
UPDATE=false
VERSION="latest"

while [[ $# -gt 0 ]]; do
    case $1 in
        --update|-u)
            UPDATE=true
            shift
            ;;
        --version|-v)
            VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--update] [--version VERSION]"
            exit 1
            ;;
    esac
done

# Banner
cat << "EOF"
╔════════════════════════════════════════════╗
║                                            ║
║         🎯 TAKTIK BOT INSTALLER           ║
║                                            ║
╚════════════════════════════════════════════╝
EOF

# Check Python version
print_info "\n[1/6] Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    print_error "❌ Python not found. Please install Python 3.10+"
    exit 1
fi

PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 10 ]); then
    print_error "❌ Python 3.10+ required. Found: Python $PYTHON_VERSION"
    exit 1
fi
print_success "✓ Python version OK: Python $PYTHON_VERSION"

# Check Git
print_info "\n[2/6] Checking Git installation..."
if ! command -v git &> /dev/null; then
    print_error "❌ Git not found. Please install Git first."
    exit 1
fi
GIT_VERSION=$(git --version)
print_success "✓ Git found: $GIT_VERSION"

# Determine installation directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"

if [ "$UPDATE" = true ]; then
    print_info "\n[3/6] Updating Taktik Bot..."
    
    # Check if we're in a git repository
    if [ -d "$INSTALL_DIR/.git" ]; then
        cd "$INSTALL_DIR"
        
        # Fetch latest changes
        print_info "Fetching latest changes..."
        git fetch origin
        
        # Get current branch
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        print_info "Current branch: $CURRENT_BRANCH"
        
        if [ "$VERSION" = "latest" ]; then
            # Pull latest from current branch
            print_info "Pulling latest changes..."
            git pull origin "$CURRENT_BRANCH"
        else
            # Checkout specific version/tag
            print_info "Checking out version $VERSION..."
            git checkout "$VERSION"
        fi
        
        print_success "✓ Repository updated successfully"
    else
        print_error "❌ Not a git repository. Cannot update."
        exit 1
    fi
else
    print_info "\n[3/6] Repository already cloned"
fi

# Install/Update dependencies
print_info "\n[4/6] Installing/Updating dependencies..."
cd "$INSTALL_DIR"
$PYTHON_CMD -m pip install --upgrade pip
$PYTHON_CMD -m pip install -r requirements.txt
print_success "✓ Dependencies installed successfully"

# Install package in development mode
print_info "\n[5/6] Installing Taktik Bot..."
$PYTHON_CMD -m pip install -e .
print_success "✓ Taktik Bot installed successfully"

# Verify installation
print_info "\n[6/6] Verifying installation..."
TAKTIK_VERSION=$($PYTHON_CMD -c "from taktik import __version__; print(__version__)" 2>&1 || echo "unknown")
if [ "$TAKTIK_VERSION" != "unknown" ]; then
    print_success "✓ Installation verified. Version: $TAKTIK_VERSION"
else
    print_warning "⚠ Could not verify installation"
fi

# Success message
cat << "EOF"

╔════════════════════════════════════════════╗
║                                            ║
║     ✅ INSTALLATION COMPLETED!            ║
║                                            ║
╚════════════════════════════════════════════╝

EOF

print_info "🚀 Quick Start:"
echo "   python -m taktik"
echo ""
print_info "📚 Documentation:"
echo "   https://taktik-bot.com/en/docs"
echo ""
print_info "🔄 To update later, run:"
echo "   ./scripts/install.sh --update"
echo ""
