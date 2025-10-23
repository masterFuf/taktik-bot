# Taktik Bot - Installation/Update Script
# This script installs or updates Taktik Bot to the latest version

param(
    [switch]$Update,
    [string]$Version = "latest"
)

$ErrorActionPreference = "Stop"

# Colors
function Write-Success { Write-Host $args -ForegroundColor Green }
function Write-Info { Write-Host $args -ForegroundColor Cyan }
function Write-Warning { Write-Host $args -ForegroundColor Yellow }
function Write-Error { Write-Host $args -ForegroundColor Red }

# Banner
Write-Host @"
╔════════════════════════════════════════════╗
║                                            ║
║         🎯 TAKTIK BOT INSTALLER           ║
║                                            ║
╚════════════════════════════════════════════╝
"@ -ForegroundColor Cyan

# Check Python version
Write-Info "`n[1/6] Checking Python version..."
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -match "Python (\d+)\.(\d+)") {
        $major = [int]$matches[1]
        $minor = [int]$matches[2]
        if ($major -lt 3 -or ($major -eq 3 -and $minor -lt 10)) {
            Write-Error "❌ Python 3.10+ required. Found: $pythonVersion"
            exit 1
        }
        Write-Success "✓ Python version OK: $pythonVersion"
    }
} catch {
    Write-Error "❌ Python not found. Please install Python 3.10+"
    exit 1
}

# Check if git is installed
Write-Info "`n[2/6] Checking Git installation..."
try {
    $gitVersion = git --version 2>&1
    Write-Success "✓ Git found: $gitVersion"
} catch {
    Write-Error "❌ Git not found. Please install Git first."
    exit 1
}

# Determine installation directory
$installDir = $PSScriptRoot | Split-Path -Parent

if ($Update) {
    Write-Info "`n[3/6] Updating Taktik Bot..."
    
    # Check if we're in a git repository
    if (Test-Path (Join-Path $installDir ".git")) {
        Push-Location $installDir
        try {
            # Fetch latest changes
            Write-Info "Fetching latest changes..."
            git fetch origin
            
            # Get current and latest version
            $currentBranch = git rev-parse --abbrev-ref HEAD
            Write-Info "Current branch: $currentBranch"
            
            if ($Version -eq "latest") {
                # Pull latest from current branch
                Write-Info "Pulling latest changes..."
                git pull origin $currentBranch
            } else {
                # Checkout specific version/tag
                Write-Info "Checking out version $Version..."
                git checkout $Version
            }
            
            Write-Success "✓ Repository updated successfully"
        } catch {
            Write-Error "❌ Failed to update repository: $_"
            Pop-Location
            exit 1
        }
        Pop-Location
    } else {
        Write-Error "❌ Not a git repository. Cannot update."
        exit 1
    }
} else {
    Write-Info "`n[3/6] Repository already cloned"
}

# Install/Update dependencies
Write-Info "`n[4/6] Installing/Updating dependencies..."
Push-Location $installDir
try {
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    Write-Success "✓ Dependencies installed successfully"
} catch {
    Write-Error "❌ Failed to install dependencies: $_"
    Pop-Location
    exit 1
}
Pop-Location

# Install package in development mode
Write-Info "`n[5/6] Installing Taktik Bot..."
Push-Location $installDir
try {
    pip install -e .
    Write-Success "✓ Taktik Bot installed successfully"
} catch {
    Write-Error "❌ Failed to install Taktik Bot: $_"
    Pop-Location
    exit 1
}
Pop-Location

# Verify installation
Write-Info "`n[6/6] Verifying installation..."
try {
    $taktikVersion = python -c "from taktik import __version__; print(__version__)" 2>&1
    Write-Success "✓ Installation verified. Version: $taktikVersion"
} catch {
    Write-Warning "⚠ Could not verify installation"
}

# Success message
Write-Host @"

╔════════════════════════════════════════════╗
║                                            ║
║     ✅ INSTALLATION COMPLETED!            ║
║                                            ║
╚════════════════════════════════════════════╝

"@ -ForegroundColor Green

Write-Info "🚀 Quick Start:"
Write-Host "   python -m taktik" -ForegroundColor White
Write-Host ""
Write-Info "📚 Documentation:"
Write-Host "   https://taktik-bot.com/en/docs" -ForegroundColor White
Write-Host ""
Write-Info "🔄 To update later, run:"
Write-Host "   .\scripts\install.ps1 -Update" -ForegroundColor White
Write-Host ""
