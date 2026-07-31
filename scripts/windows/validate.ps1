# setupfix11.2.2.2-v1: canonical validate command.
param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-CollectorCommand -CliArguments @('validate') -PauseOnExit:$PauseOnExit
