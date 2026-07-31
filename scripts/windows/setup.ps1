param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Initialize-Console
$root = Get-ProjectRoot
foreach ($name in @('logs', 'data', 'input', 'output')) {
    New-Item -ItemType Directory -Force -Path (Join-Path $root $name) | Out-Null
}
$log = Join-Path $root ("logs\setup_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
Start-Transcript -LiteralPath $log -Force | Out-Null
$code = 1
try {
    Write-Host '営業リスト収集システムのセットアップを開始します。'
    $python = Find-Python313 -Root $root
    if ($null -eq $python) {
        Write-Host 'Python 3.13が見つかりません。Python公式サイトから64bit版をインストールしてください。'
        Write-Host 'Microsoft Storeが開く場合は「アプリ実行エイリアス」のpythonを無効にしてください。'
        $code = 2
    } else {
        $bits = & $python.Exe @($python.Prefix) -c 'import struct; print(struct.calcsize("P")*8)'
        if ($bits.Trim() -ne '64') { Write-Warning '64bit版Python 3.13を推奨します。' }
        $venvPython = Join-Path $root '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $venvPython)) {
            $result = Invoke-Python313 $python @('-m', 'venv', (Join-Path $root '.venv'))
            if ($result -ne 0) { throw '.venvの作成に失敗しました。' }
        }
        & $venvPython -m pip install --upgrade pip
        if ($LASTEXITCODE -ne 0) { throw 'pipの更新に失敗しました。' }
        & $venvPython -m pip install -r (Join-Path $root 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'requirements.txtのインストールに失敗しました。' }
        $enabled = & $venvPython -c "import yaml; print(str(yaml.safe_load(open('config/default.yaml',encoding='utf-8'))['crawler']['playwright']['enabled']).lower())"
        if ($enabled.Trim() -eq 'true') {
            & $venvPython -m playwright install chromium
            if ($LASTEXITCODE -ne 0) { Write-Warning 'Chromium導入失敗。requestsのみで運用します。' }
        } else { Write-Host 'Playwrightは無効のためChromiumをインストールしません。' }
        $sample = Join-Path $root 'input\search_conditions_sample.csv'
        $actual = Join-Path $root 'input\search_conditions.csv'
        if (-not (Test-Path -LiteralPath $actual)) { Copy-Item -LiteralPath $sample -Destination $actual }
        & $venvPython -m src.cli validate
        $code = $LASTEXITCODE
        if ($code -eq 0) { Write-Host 'セットアップが正常に完了しました。' -ForegroundColor Green }
        else { Write-Host "validateに失敗しました（終了コード: $code）。" -ForegroundColor Red }
    }
} catch {
    Write-Host $_.Exception.ToString() -ForegroundColor Red
    Write-Host $_.ScriptStackTrace
    $code = 1
} finally {
    Stop-Transcript | Out-Null
    Write-Host "セットアップログ: $log"
    if ($PauseOnExit) { Read-Host 'Enterキーを押して閉じてください' | Out-Null }
}
exit $code
