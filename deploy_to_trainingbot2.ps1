# ═══════════════════════════════════════════════════════════════
# NEO AI — Auto-Deploy Script for TRAININGBOT2 (Windows)
# Run in PowerShell: .\deploy_to_trainingbot2.ps1
# ═══════════════════════════════════════════════════════════════

$ErrorActionPreference = "Stop"

# ─── CONFIG ───
$ProjectRoot = "C:\Users\fundi\OneDrive\Documents\TRAININGBOT2"
$DownloadDir = "$env:USERPROFILE\Downloads"  # Adjust if files are elsewhere

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     NEO AI — Deploy Files to TRAININGBOT2                   ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Verify TRAININGBOT2 exists ───
if (-not (Test-Path $ProjectRoot)) {
    Write-Error "❌ TRAININGBOT2 not found at: $ProjectRoot"
    exit 1
}

Write-Host "✅ Found TRAININGBOT2 at: $ProjectRoot" -ForegroundColor Green
Write-Host ""

# ─── Create .github/workflows folder ───
$GithubDir = Join-Path $ProjectRoot ".github\workflows"
if (-not (Test-Path $GithubDir)) {
    New-Item -ItemType Directory -Force -Path $GithubDir | Out-Null
    Write-Host "📁 Created: .github\workflows" -ForegroundColor Yellow
}

# ─── File mapping: Source → Destination ───
$Files = @(
    @{ Source="wsgi.py"; Dest="$ProjectRoot\wsgi.py"; Required=$true },
    @{ Source="Dockerfile"; Dest="$ProjectRoot\Dockerfile"; Required=$true },
    @{ Source="requirements.txt"; Dest="$ProjectRoot\requirements.txt"; Required=$true },
    @{ Source="docker-compose.yml"; Dest="$ProjectRoot\docker-compose.yml"; Required=$true },
    @{ Source="ecosystem.config.js"; Dest="$ProjectRoot\ecosystem.config.js"; Required=$true },
    @{ Source="setup.sh"; Dest="$ProjectRoot\setup.sh"; Required=$true },
    @{ Source="nginx.conf"; Dest="$ProjectRoot\nginx.conf"; Required=$false },
    @{ Source="deploy.yml"; Dest="$GithubDir\deploy.yml"; Required=$true }
)

# ─── Copy each file ───
$Copied = 0
$Skipped = 0

foreach ($File in $Files) {
    $SrcPath = Join-Path $DownloadDir $File.Source
    $DestPath = $File.Dest

    if (Test-Path $SrcPath) {
        Copy-Item -Path $SrcPath -Destination $DestPath -Force
        Write-Host "  ✅ $($File.Source) → $DestPath" -ForegroundColor Green
        $Copied++
    } else {
        if ($File.Required) {
            Write-Host "  ⚠️  MISSING (required): $($File.Source) — expected at $SrcPath" -ForegroundColor Red
        } else {
            Write-Host "  ⏭️  Skipped (optional): $($File.Source)" -ForegroundColor Gray
        }
        $Skipped++
    }
}

Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║              DEPLOY SUMMARY                                  ║" -ForegroundColor Cyan
Write-Host "╠══════════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
Write-Host "║  Files copied:    $Copied" -ForegroundColor Green
Write-Host "║  Files skipped:    $Skipped" -ForegroundColor $(if ($Skipped -gt 0) { "Yellow" } else { "Green" })
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ─── Verify final structure ───
Write-Host "📂 Final TRAININGBOT2 structure:" -ForegroundColor Cyan
$Tree = @"
TRAININGBOT2/
├── wsgi.py                    ← NEW (Gunicorn entry point)
├── Dockerfile                 ← NEW (Production build)
├── requirements.txt           ← NEW (Production deps)
├── docker-compose.yml         ← NEW (Full stack)
├── ecosystem.config.js        ← NEW (PM2 process manager)
├── setup.sh                   ← NEW (Server setup script)
├── nginx.conf                 ← NEW (Reverse proxy)
├── .github/
│   └── workflows/
│       └── deploy.yml         ← NEW (CI/CD pipeline)
├── launcher.py                ← EXISTING (your launcher)
├── neo_chat.html              ← EXISTING (your web UI)
├── core/                      ← EXISTING (your modules)
├── data/                      ← EXISTING
└── .env                       ← EXISTING (your secrets)
"@
Write-Host $Tree -ForegroundColor White

Write-Host ""
Write-Host "🚀 Next steps:" -ForegroundColor Cyan
Write-Host "  1. Rename launcher_fixed.py → launcher.py (if you haven't)" -ForegroundColor White
Write-Host "  2. Update REPO_URL in setup.sh and ecosystem.config.js" -ForegroundColor White
Write-Host "  3. Add GitHub secrets: RENDER_SERVICE_ID, RENDER_API_KEY" -ForegroundColor White
Write-Host "  4. Add GitHub secrets: ORACLE_HOST, ORACLE_SSH_KEY" -ForegroundColor White
Write-Host "  5. Commit and push: git add . && git commit -m 'Production deploy' && git push" -ForegroundColor White
Write-Host "  6. Deploy to Render or Oracle Cloud" -ForegroundColor White
