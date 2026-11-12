$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Create the project environment first: py -m venv .venv"
}

& $python -m pip install -r requirements-build.txt
if ($LASTEXITCODE -ne 0) {
    throw "Could not install the application build dependencies."
}

$browserPath = Join-Path $projectRoot "build\playwright-browsers"
$previousBrowserPath = $env:PLAYWRIGHT_BROWSERS_PATH
$env:PLAYWRIGHT_BROWSERS_PATH = $browserPath
try {
    & $python -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Could not install Playwright Chromium."
    }

    & $python -m PyInstaller `
        --noconfirm `
        --clean `
        --onedir `
        --console `
        --name CNAWritingGrader `
        --collect-all playwright `
        --distpath (Join-Path $projectRoot "dist") `
        --workpath (Join-Path $projectRoot "build\pyinstaller") `
        --specpath (Join-Path $projectRoot "build\spec") `
        (Join-Path $projectRoot "grade_cna.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller could not build CNA Writing Grader."
    }

    $bundlePath = Join-Path $projectRoot "dist\CNAWritingGrader"
    $bundledBrowserPath = Join-Path $bundlePath "ms-playwright"
    New-Item -ItemType Directory -Path $bundledBrowserPath -Force | Out-Null
    Get-ChildItem -Path $browserPath | Copy-Item -Destination $bundledBrowserPath -Recurse -Force
    Copy-Item -Path (Join-Path $projectRoot "README.md") -Destination $bundlePath
    Copy-Item -Path (Join-Path $projectRoot "WINDOWS_SETUP.md") -Destination $bundlePath

    $archivePath = Join-Path $projectRoot "dist\CNAWritingGrader-win-x64.zip"
    Compress-Archive -Path $bundlePath -DestinationPath $archivePath -Force
    Write-Host "Built executable: $(Join-Path $bundlePath 'CNAWritingGrader.exe')"
    Write-Host "Distribution archive: $archivePath"
}
finally {
    if ($null -eq $previousBrowserPath) {
        Remove-Item Env:PLAYWRIGHT_BROWSERS_PATH -ErrorAction SilentlyContinue
    }
    else {
        $env:PLAYWRIGHT_BROWSERS_PATH = $previousBrowserPath
    }
}
