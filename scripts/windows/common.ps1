# setupfix11.2.2-v1: canonical Windows PowerShell 5.1 launcher functions.
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

function Get-ProjectRoot {
    [CmdletBinding()]
    param()
    return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
}

function Initialize-Console {
    [CmdletBinding()]
    param()
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::InputEncoding = $utf8
    [Console]::OutputEncoding = $utf8
    $script:OutputEncoding = $utf8
    Set-Location -LiteralPath (Get-ProjectRoot)
}

function Find-Python313 {
    [CmdletBinding()]
    param([string]$Root = (Get-ProjectRoot))
    $candidates = New-Object System.Collections.ArrayList
    $venv = Join-Path $Root '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venv) {
        [void]$candidates.Add([pscustomobject]@{ Exe = $venv; Prefix = @() })
    }
    [void]$candidates.Add([pscustomobject]@{ Exe = 'py'; Prefix = @('-3.13') })
    [void]$candidates.Add([pscustomobject]@{ Exe = 'python'; Prefix = @() })
    [void]$candidates.Add([pscustomobject]@{ Exe = 'python3'; Prefix = @() })
    foreach ($candidate in $candidates) {
        try {
            $probe = & $candidate.Exe @($candidate.Prefix) -c `
                'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null
            if ($LASTEXITCODE -eq 0 -and "$probe".Trim() -eq '3.13') {
                return [pscustomobject]@{ Exe = $candidate.Exe; Prefix = $candidate.Prefix }
            }
        } catch {
            continue
        }
    }
    return $null
}

function Invoke-Python313 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Python,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )
    & $Python.Exe @($Python.Prefix) @Arguments
    return [int]$LASTEXITCODE
}

function Invoke-CollectorCommand {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string[]]$CliArguments,
        [switch]$PauseOnExit
    )
    Initialize-Console
    $root = Get-ProjectRoot
    $logDir = Join-Path $root 'logs'
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $log = Join-Path $logDir ("launcher_{0:yyyyMMdd_HHmmss}.log" -f (Get-Date))
    Start-Transcript -LiteralPath $log -Force | Out-Null
    [int]$code = 1
    try {
        $python = Find-Python313 -Root $root
        if ($null -eq $python) {
            throw 'Python 3.13が見つかりません。setup.batを実行してください。'
        }
        [int]$code = Invoke-Python313 -Python $python `
            -Arguments (@('-m', 'src.cli') + $CliArguments)
        if ($code -eq 0) {
            Write-Host '正常に完了しました。' -ForegroundColor Green
        } else {
            Write-Host "処理に失敗しました（終了コード: $code）。ログ: $log" `
                -ForegroundColor Red
        }
    } catch {
        Write-Host $_.Exception.ToString() -ForegroundColor Red
        Write-Host $_.ScriptStackTrace
        [int]$code = 1
    } finally {
        try { Stop-Transcript | Out-Null } catch { }
        if ($PauseOnExit) {
            Write-Host 'Press any key to continue . . .'
            [void][Console]::ReadKey($true)
        }
    }
    exit ([int]$code)
}
