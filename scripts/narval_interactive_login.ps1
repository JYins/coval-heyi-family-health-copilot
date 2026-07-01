param(
    [string]$HostAlias = "narval"
)

$ErrorActionPreference = "Stop"

Write-Host "Opening plain Narval SSH login."
Write-Host "Command: ssh ${HostAlias}"
Write-Host "If asked for key passphrase and the key has no passphrase, press Enter."
Write-Host "After login, run: exit"

ssh "${HostAlias}"
