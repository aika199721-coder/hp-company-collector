param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Initialize-Console
$root = Get-ProjectRoot
$logs = Join-Path $root 'logs'
New-Item -ItemType Directory -Force -Path $logs | Out-Null
$out = Join-Path $logs ("diagnostics_{0:yyyyMMdd_HHmmss}.txt" -f (Get-Date))
try {
    $python = Find-Python313 -Root $root
    $pathFlags = @(
        "日本語=$([bool]($root -match '[^\x00-\x7F]'))",
        "空白=$($root.Contains(' '))", "括弧=$([bool]($root -match '[()]'))",
        "OneDrive=$($root -match 'OneDrive')"
    ) -join ', '
    $lines = @("Windows: $([Environment]::OSVersion.VersionString)", "Project: $root", "Path flags: $pathFlags")
    if ($null -eq $python) { $lines += 'Python 3.13: 利用不可' }
    else {
        $lines += "Python path: $($python.Exe)"
        $lines += "Python version: $(& $python.Exe @($python.Prefix) --version 2>&1)"
        $lines += "Python bits: $(& $python.Exe @($python.Prefix) -c 'import struct; print(struct.calcsize("P")*8)')"
        $lines += "pip: $(& $python.Exe @($python.Prefix) -m pip --version 2>&1)"
        $lines += "Packages: $(& $python.Exe @($python.Prefix) -m pip show requests beautifulsoup4 openpyxl PyYAML playwright 2>&1 | Select-String '^(Name|Version):')"
        $lines += "Playwright import: $(& $python.Exe @($python.Prefix) -c 'import importlib.util; print(importlib.util.find_spec("playwright") is not None)')"
    }
    $lines += "Virtual environment: $(Test-Path -LiteralPath (Join-Path $root '.venv\Scripts\python.exe'))"
    foreach ($file in @('config\default.yaml','config\providers.yaml','config\pipeline.yaml','config\scoring.yaml','input\search_conditions.csv','data\collector.sqlite3')) {
        $lines += "$file exists: $(Test-Path -LiteralPath (Join-Path $root $file))"
    }
    foreach ($dir in @('logs','data','input','output')) {
        $probe = Join-Path $root "$dir\.write_test"
        try { 'test' | Set-Content -LiteralPath $probe; Remove-Item -LiteralPath $probe; $ok = $true } catch { $ok = $false }
        $lines += "$dir writable: $ok"
    }
    $db = Join-Path $root 'data\collector.sqlite3'
    if ((Test-Path $db) -and $null -ne $python) {
        $lines += "SQLite schema: $(& $python.Exe @($python.Prefix) -c 'import sqlite3; print(sqlite3.connect(r"data/collector.sqlite3").execute("PRAGMA user_version").fetchone()[0])')"
        $lines += "Latest run status: $(& $python.Exe @($python.Prefix) -c 'import sqlite3; c=sqlite3.connect(r"data/collector.sqlite3"); print((c.execute("SELECT status FROM runs ORDER BY started_at DESC LIMIT 1").fetchone() or ["なし"])[0])' 2>$null)"
    }
    $latest = Get-ChildItem -LiteralPath $logs -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    $lines += "Latest log: $($latest.Name)"
    $lines | Set-Content -LiteralPath $out -Encoding utf8
    Write-Host "診断ファイルを作成しました: $out" -ForegroundColor Green
    $code = 0
} catch { $_.Exception.ToString() | Set-Content -LiteralPath $out; Write-Host $_.Exception; $code = 1 }
if ($PauseOnExit) { Read-Host 'Enterキーを押して閉じてください' | Out-Null }
exit $code
