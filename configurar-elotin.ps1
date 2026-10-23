$ErrorActionPreference = 'Stop'
$configPath = Join-Path $PSScriptRoot '.env'
$modelId = 'openai/gpt-oss-20b'
$secureKey = Read-Host 'Clave API de Groq Console (no se muestra al escribir)' -AsSecureString
$keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $newKey = ([Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer)).Trim()
    if ([string]::IsNullOrWhiteSpace($newKey)) { throw 'No se recibió una clave. Usa Copiar clave en Groq Console y pégala con Ctrl+V o clic derecho; después pulsa Enter. La entrada permanece oculta.' }
    if ($newKey -match '^sk-') { throw 'Se recibió una clave de OpenAI. Copia la clave de Groq Console para configurar Groq.' }
    if ($newKey -notmatch '^gsk_[A-Za-z0-9_-]{20,}$') { throw 'No se recibió una clave completa de Groq Console. Usa Copiar clave; no copies el nombre, el ID del proyecto, el modelo ni la terminación abreviada. No se guardaron cambios.' }
    $preservedLines = @()
    if (Test-Path -LiteralPath $configPath) {
        $preservedLines = @(Get-Content -LiteralPath $configPath | Where-Object { $_ -notmatch '^\s*(OPENAI|GEMINI|GROQ)_(API_KEY|MODEL)\s*=' })
    }
    $configLines = @($preservedLines) + @("GROQ_API_KEY=$newKey", "GROQ_MODEL=$modelId")
    [IO.File]::WriteAllLines($configPath, $configLines, [Text.UTF8Encoding]::new($false))
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer)
    $newKey = $null
    $configLines = $null
    $secureKey.Dispose()
}
Write-Host 'Configuración local guardada. No se realizó ninguna consulta de pago.'
Write-Host 'Recarga SIMAC, abre Elotín y activa Usar IA. La guía local permanece disponible.'
