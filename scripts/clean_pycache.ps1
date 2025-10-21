# Script PowerShell pour nettoyer tous les __pycache__ et fichiers .pyc
Write-Host "Nettoyage des fichiers cache Python..." -ForegroundColor Cyan
Write-Host ""

# Compter les fichiers avant nettoyage
$pycacheDirs = Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue
$pycFiles = Get-ChildItem -Path . -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue

$pycacheDirsCount = ($pycacheDirs | Measure-Object).Count
$pycFilesCount = ($pycFiles | Measure-Object).Count

Write-Host "Fichiers trouves:" -ForegroundColor Yellow
Write-Host "   - Dossiers __pycache__: $pycacheDirsCount" -ForegroundColor White
Write-Host "   - Fichiers .pyc: $pycFilesCount" -ForegroundColor White
Write-Host ""

if ($pycacheDirsCount -eq 0 -and $pycFilesCount -eq 0) {
    Write-Host "Aucun fichier cache a nettoyer!" -ForegroundColor Green
    exit 0
}

# Supprimer les dossiers __pycache__
if ($pycacheDirsCount -gt 0) {
    Write-Host "Suppression des dossiers __pycache__..." -ForegroundColor Yellow
    $pycacheDirs | ForEach-Object {
        Write-Host "   Suppression: $($_.FullName)" -ForegroundColor DarkGray
        Remove-Item -Path $_.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "   OK - $pycacheDirsCount dossiers __pycache__ supprimes" -ForegroundColor Green
}

# Supprimer les fichiers .pyc
if ($pycFilesCount -gt 0) {
    Write-Host "Suppression des fichiers .pyc..." -ForegroundColor Yellow
    $pycFiles | ForEach-Object {
        Write-Host "   Suppression: $($_.FullName)" -ForegroundColor DarkGray
        Remove-Item -Path $_.FullName -Force -ErrorAction SilentlyContinue
    }
    Write-Host "   OK - $pycFilesCount fichiers .pyc supprimes" -ForegroundColor Green
}

Write-Host ""
Write-Host "Nettoyage termine avec succes!" -ForegroundColor Green
Write-Host ""
