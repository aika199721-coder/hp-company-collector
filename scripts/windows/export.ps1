param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-CollectorCommand -CliArguments @('export') -PauseOnExit:$PauseOnExit
