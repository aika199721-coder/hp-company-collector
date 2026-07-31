param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-CollectorCommand -CliArguments @('reset-retries', '--yes') -PauseOnExit:$PauseOnExit
