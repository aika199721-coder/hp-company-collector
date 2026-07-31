# setupfix11.2.2.2-v1: canonical Windows PowerShell 5.1 launcher functions.
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

function Add-PythonCandidate {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [System.Collections.ArrayList]$Candidates,
        [string]$Exe,
        [string[]]$Prefix = @(),
        [string]$Source
    )
    if ([string]::IsNullOrWhiteSpace($Exe)) { return }
    $candidatePath = $Exe.Trim().Trim('"')
    if ((Test-Path -LiteralPath $candidatePath -PathType Container)) {
        $candidatePath = Join-Path $candidatePath 'python.exe'
    }
    $key = "$candidatePath|$($Prefix -join ' ')"
    if (-not ($Candidates | Where-Object { $_.Key -eq $key })) {
        [void]$Candidates.Add([pscustomobject]@{
            Exe = $candidatePath
            Prefix = $Prefix
            Source = $Source
            Key = $key
        })
    }
}

function Get-PythonCandidates {
    [CmdletBinding()]
    param([string]$Root = (Get-ProjectRoot))
    $candidates = New-Object System.Collections.ArrayList
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($null -ne $command) {
        $commandPath = if ($command.Source) { $command.Source } else { $command.Path }
        Add-PythonCandidate -Candidates $candidates -Exe $commandPath `
            -Prefix @() -Source 'Get-Command python.exe'
    }
    try {
        $whereResults = & where.exe python 2>$null
        foreach ($path in @($whereResults)) {
            Add-PythonCandidate -Candidates $candidates -Exe "$path" `
                -Prefix @() -Source 'where.exe python'
        }
    } catch { }
    if (-not [string]::IsNullOrWhiteSpace($env:pythonLocation)) {
        Add-PythonCandidate -Candidates $candidates `
            -Exe (Join-Path $env:pythonLocation 'python.exe') `
            -Prefix @() -Source 'pythonLocation'
    }
    if (-not [string]::IsNullOrWhiteSpace($env:Python_ROOT_DIR)) {
        Add-PythonCandidate -Candidates $candidates `
            -Exe (Join-Path $env:Python_ROOT_DIR 'python.exe') `
            -Prefix @() -Source 'Python_ROOT_DIR'
    }
    Add-PythonCandidate -Candidates $candidates -Exe 'py' `
        -Prefix @('-3.13') -Source 'py -3.13'
    Add-PythonCandidate -Candidates $candidates -Exe 'python' -Prefix @() -Source 'python'
    Add-PythonCandidate -Candidates $candidates -Exe 'python3' -Prefix @() -Source 'python3'
    return @($candidates.ToArray())
}

function Test-PythonCandidate {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Candidate)
    $exe = "$($Candidate.Exe)"
    if ($Candidate.Source -eq 'HPCC_PYTHON' -and
        -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        Write-Host "Python候補を除外 (HPCC_PYTHON実体なし): $exe"
        return $null
    }
    if ($exe -notmatch '[\\/:]') {
        $resolved = Get-Command $exe -ErrorAction SilentlyContinue
        if ($null -eq $resolved) { return $null }
        if ($resolved.Source -match '(?i)\\WindowsApps\\') {
            Write-Host "Python候補を除外 (Microsoft Store alias): $($resolved.Source)"
            return $null
        }
    }
    if ($exe -match '(?i)\\WindowsApps\\') {
        Write-Host "Python候補を除外 (Microsoft Store alias): $exe"
        return $null
    }
    if (($exe -match '[\\/:]') -and -not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        Write-Host "Python候補を除外 (実体なし): $exe"
        return $null
    }
    try {
        $probeArguments = @($Candidate.Prefix) + @(
            '-c',
            'import sys, struct; print(sys.executable); print("%d.%d" % sys.version_info[:2]); print(struct.calcsize("P") * 8)'
        )
        $probe = & $exe @probeArguments 2>&1
        [int]$probeExitCode = $LASTEXITCODE
        if ($probeExitCode -ne 0 -or @($probe).Count -lt 3) {
            $probeOutput = @($probe) -join [Environment]::NewLine
            Write-Host "Python候補のprobe失敗 [$($Candidate.Source)]: " `
                "exit=$probeExitCode output=$probeOutput"
            return $null
        }
        $path = "$($probe[0])".Trim()
        $version = "$($probe[1])".Trim()
        [int]$bits = "$($probe[2])".Trim()
        Write-Host "Python候補 [$($Candidate.Source)]: $path version=$version bits=$bits"
        if ($path -match '(?i)\\WindowsApps\\') { return $null }
        if ($version -ne '3.13' -or $bits -ne 64) { return $null }
        return [pscustomobject]@{
            Exe = $exe
            Prefix = $Candidate.Prefix
            Source = $Candidate.Source
            Path = $path
            Version = $version
            Bits = $bits
        }
    } catch {
        Write-Host "Python候補の検証例外 [$($Candidate.Source)]: $($_.Exception.Message)"
        return $null
    }
}

function Write-PythonDiagnostics {
    [CmdletBinding()]
    param()
    Write-Host "PATH: $env:PATH"
    Write-Host "HPCC_PYTHON: $env:HPCC_PYTHON"
    Write-Host "pythonLocation: $env:pythonLocation"
    Write-Host "Python_ROOT_DIR: $env:Python_ROOT_DIR"
    try { Write-Host "where python: $(& where.exe python 2>&1 | Out-String)" } catch { }
    $command = Get-Command python.exe -ErrorAction SilentlyContinue
    $commandPath = if ($null -ne $command) { $command.Source } else { '' }
    Write-Host "Get-Command python.exe: $commandPath"
}

function Find-Python313 {
    [CmdletBinding()]
    param([string]$Root = (Get-ProjectRoot))
    Write-PythonDiagnostics
    if (-not [string]::IsNullOrWhiteSpace($env:HPCC_PYTHON)) {
        $configuredCandidates = New-Object System.Collections.ArrayList
        Add-PythonCandidate -Candidates $configuredCandidates -Exe $env:HPCC_PYTHON `
            -Prefix @() -Source 'HPCC_PYTHON'
        $configured = $configuredCandidates[0]
        $accepted = Test-PythonCandidate -Candidate $configured
        if ($null -ne $accepted) {
            Write-Host "最終採用Python: $($accepted.Path)"
            Write-Host "Python version: $($accepted.Version)"
            Write-Host "Python bit数: $($accepted.Bits)"
            return $accepted
        }
    }
    $candidates = @(Get-PythonCandidates -Root $Root)
    if ($candidates.Count -eq 0) {
        Write-Information 'Python 3.13候補が見つかりません' -InformationAction Continue
        return $null
    }
    foreach ($candidate in $candidates) {
        $accepted = Test-PythonCandidate -Candidate $candidate
        if ($null -ne $accepted) {
            Write-Host "最終採用Python: $($accepted.Path)"
            Write-Host "Python version: $($accepted.Version)"
            Write-Host "Python bit数: $($accepted.Bits)"
            return $accepted
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
    $invokeArguments = @($Python.Prefix) + @($Arguments)
    & $Python.Exe @invokeArguments
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
            throw '64bit Python 3.13が見つかりません。setup.batを実行してください。'
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
