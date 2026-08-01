# setupfix11.2.2.2-v1: canonical Windows PowerShell 5.1 setup.
param([switch]$NonInteractive)
. (Join-Path $PSScriptRoot 'common.ps1')
Initialize-Console
$root = Get-ProjectRoot
foreach ($name in @('logs', 'data', 'input', 'output')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $name) | Out-Null
}
$log = Join-Path $root ("logs\setup_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
Start-Transcript -LiteralPath $log -Force | Out-Null
[int]$code = 1
$detectedPython = Find-Python313 -Root $root
$PythonExe = $null
if ($null -ne $detectedPython) { $PythonExe = $detectedPython.Path }
try {
    Write-Host '営業リスト収集システムのセットアップを開始します。'
    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        Write-Host 'Python 3.13が見つかりません。Python公式サイトから64bit版を導入してください。'
        Write-Host 'Microsoft Storeが開く場合はアプリ実行エイリアスのpythonを無効にしてください。'
        [int]$code = 2
    } else {
        $bitsCode = "import struct; print(struct.calcsize('P') * 8)"
        $bitsArguments = @('-c', $bitsCode)
        $bits = & $PythonExe @bitsArguments
        if ($LASTEXITCODE -ne 0) { throw 'Python bit数の確認に失敗しました。' }
        if ("$bits".Trim() -ne '64') { Write-Warning '64bit版Python 3.13を推奨します。' }
        $venvPython = Join-Path $root '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $venvPython)) {
            & $PythonExe -m venv (Join-Path $root '.venv')
            if ($LASTEXITCODE -ne 0) { throw '.venvの作成に失敗しました。' }
        }
        $venvCandidate = [pscustomobject]@{
            Exe = $venvPython
            Prefix = @()
            Source = '.venv'
        }
        $confirmedVenv = Test-PythonCandidate -Candidate $venvCandidate
        if ($null -eq $confirmedVenv) { throw '.venvのPython確認に失敗しました。' }
        $PythonExe = $confirmedVenv.Path
        & $PythonExe -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'pipの更新に失敗しました。' }
        & $PythonExe -m pip install -r (Join-Path $root 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'requirements.txtの導入に失敗しました。' }
        $playwrightCode = "import yaml; print(str(yaml.safe_load(open('config/default.yaml', encoding='utf-8'))['crawler']['playwright']['enabled']).lower())"
        $playwrightArguments = @('-c', $playwrightCode)
        $enabled = & $PythonExe @playwrightArguments
        if ($LASTEXITCODE -ne 0) { throw 'Playwright設定の確認に失敗しました。' }
        if ("$enabled".Trim() -eq 'true') {
            & $PythonExe -m playwright install chromium
            if ($LASTEXITCODE -ne 0) {
                Write-Warning 'Chromium導入失敗。requestsのみで運用します。'
            }
        } else {
            Write-Host 'Playwrightは無効のためChromiumをインストールしません。'
        }
        $sample = Join-Path $root 'input\search_conditions_sample.csv'
        $actual = Join-Path $root 'input\search_conditions.csv'
        if (-not (Test-Path -LiteralPath $actual)) {
            Copy-Item -LiteralPath $sample -Destination $actual
        }
        & $PythonExe -m src.cli validate
        [int]$code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-Host 'セットアップが正常に完了しました。' -ForegroundColor Green
            Write-Host '次に validate.bat を実行してください。'
        } else {
            Write-Host "validateに失敗しました（終了コード: $code）。" -ForegroundColor Red
        }
    }
} catch {
    Write-Host $_.Exception.ToString() -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
    [int]$code = 1
} finally {
    try { Stop-Transcript | Out-Null } catch { }
    Write-Host "セットアップログ: $log"
}
exit ([int]$code)
