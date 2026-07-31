# Shared Windows launcher functions. No administrator rights are required.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
    [CmdletBinding()]
    param()
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
}

function Initialize-Console {
    [CmdletBinding()]
    param()
    [Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
    [Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
    $OutputEncoding = [Text.UTF8Encoding]::new($false)
    Set-Location -LiteralPath (Get-ProjectRoot)
}

function Find-Python313 {
    [CmdletBinding()]
    param([string]$Root = (Get-ProjectRoot))
    $candidates = [Collections.Generic.List[object]]::new()
    $venv = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) {
        $candidates.Add([pscustomobject]@{ Exe = $venv; Prefix = @() })
    }
    $candidates.Add([pscustomobject]@{ Exe = 'py'; Prefix = @('-3.13') })
    $candidates.Add([pscustomobject]@{ Exe = 'python'; Prefix = @() })
    $candidates.Add([pscustomobject]@{ Exe = 'python3'; Prefix = @() })
    foreach ($candidate in $candidates) {
        try {
            $exe = $candidate.Exe
            $prefix = $candidate.Prefix
            $probe = & $exe @prefix -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $probe.Trim() -eq '3.13') {
                return [pscustomobject]@{ Exe = $exe; Prefix = $prefix }
            }
        } catch { continue }
    }
    return $null
}

function Invoke-Python313 {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$Python, [Parameter(Mandatory)][string[]]$Arguments)
    & $Python.Exe @($Python.Prefix) @Arguments
    return $LASTEXITCODE
}

function Stop-WithMessage {
    [CmdletBinding()]
    param([string]$Message, [int]$Code = 1, [switch]$PauseOnExit)
    Write-Host "エラー: $Message" -ForegroundColor Red
    if ($PauseOnExit) { Read-Host 'Enterキーを押して閉じてください' | Out-Null }
    exit $Code
}

function Invoke-CollectorCommand {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string[]]$CliArguments, [switch]$PauseOnExit)
    Initialize-Console
    $root = Get-ProjectRoot
    $logDir = Join-Path $root 'logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $log = Join-Path $logDir ("launcher_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
    Start-Transcript -LiteralPath $log -Force | Out-Null
    $code = 1
    try {
        $python = Find-Python313 -Root $root
        if ($null -eq $python) {
            throw 'Python 3.13が見つかりません。setup.batを実行してください。'
        }
        $code = Invoke-Python313 -Python $python -Arguments (@('-m', 'src.cli') + $CliArguments)
        if ($code -eq 0) { Write-Host '正常に完了しました。' -ForegroundColor Green }
        else { Write-Host "処理に失敗しました（終了コード: $code）。ログ: $log" -ForegroundColor Red }
    } catch {
        Write-Host $_.Exception.ToString() -ForegroundColor Red
        Write-Host $_.ScriptStackTrace
        $code = 1
    } finally {
        Stop-Transcript | Out-Null
        if ($PauseOnExit) { Read-Host 'Enterキーを押して閉じてください' | Out-Null }
    }
    exit $code
}
