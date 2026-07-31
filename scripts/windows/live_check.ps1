# setupfix11.2.2.1-v1: canonical live validation command.
param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-CollectorCommand -CliArguments @('live-check') -PauseOnExit:$PauseOnExit
