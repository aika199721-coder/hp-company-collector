param([switch]$PauseOnExit)
. (Join-Path $PSScriptRoot 'common.ps1')
Invoke-CollectorCommand -CliArguments @('review-import', '--file', 'input/live_review.csv') -PauseOnExit:$PauseOnExit
