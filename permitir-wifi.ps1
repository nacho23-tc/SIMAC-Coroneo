$ErrorActionPreference = 'Stop'
if (-not (Get-NetFirewallRule -DisplayName 'SIMAC Coroneo - pruebas WiFi 5173' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName 'SIMAC Coroneo - pruebas WiFi 5173' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -RemoteAddress LocalSubnet -Profile Any -Program 'C:\Program Files\nodejs\node.exe'
}
