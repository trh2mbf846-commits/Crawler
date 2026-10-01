# Startet den Ausschreibungs-Crawler lokal unter Windows - per Doppelklick auf "Crawler starten.bat".
#
# Beim ersten Start wird alles Noetige eingerichtet (Python-Umgebung, Frontend-Build, optional
# Ollama-Modell fuer Crawler Kevin), danach startet nur noch der Server und oeffnet
# http://localhost:8000. Voraussetzung: Python 3.11+ und Node.js (LTS); optional Git (fuer
# automatische Updates) und Ollama (Kevin). Siehe docs/ANLEITUNG-kollegen.md.
#
# ACHTUNG: Dieses Skript konnte in der Entwicklungsumgebung nur auf Syntax und Hilfsfunktionen
# geprueft werden, nicht auf einem echten Windows-Rechner. Bitte Fehlermeldungen melden.
#
# Bewusst kompatibel mit Windows PowerShell 5.1 (keine neueren Sprachfeatures).

$ErrorActionPreference = 'Stop'
$Projekt = $PSScriptRoot
Set-Location $Projekt
$Backend = Join-Path $Projekt 'backend'
$Frontend = Join-Path $Projekt 'frontend'
$Port = 8000
$Url = "http://localhost:$Port"

function Schritt($text) { Write-Host ''; Write-Host "==> $text" -ForegroundColor Cyan }
function Hinweis($text) { Write-Host $text -ForegroundColor Yellow }
function Fehler($text) {
    Write-Host ''
    Write-Host "FEHLER: $text" -ForegroundColor Red
    Read-Host 'Mit Enter schliessen'
    exit 1
}
function Hat-Befehl($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# Fuehrt ein Programm aus, zeigt dessen Ausgabe und liefert den Exit-Code (stderr ist kein Abbruch).
function Ausfuehren {
    param([string]$Exe, [string[]]$Argumente)
    $alt = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $Exe @Argumente 2>&1 | Out-Host
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $alt
    }
}

# Wert einer Zeile NAME=wert aus backend\.env (leer, wenn nicht vorhanden).
function Env-Wert($name) {
    $datei = Join-Path $Backend '.env'
    if (-not (Test-Path $datei)) { return '' }
    $treffer = Select-String -Path $datei -Pattern "^\s*$name=(.*)$" | Select-Object -Last 1
    if ($treffer) { return $treffer.Matches[0].Groups[1].Value.Trim() }
    return ''
}

function Text-Hash($text) {
    $sha = [System.Security.Cryptography.SHA1]::Create()
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($text)
    return ([System.BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '')
}

function Crawler-Laeuft {
    try {
        $null = Invoke-WebRequest -Uri "$Url/api/health" -UseBasicParsing -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

# --- Voraussetzungen ----------------------------------------------------------------------
$Python = $null
$kandidaten = @(
    @{ Exe = 'py'; Args = @('-3.13') }, @{ Exe = 'py'; Args = @('-3.12') }, @{ Exe = 'py'; Args = @('-3.11') },
    @{ Exe = 'python'; Args = @() }, @{ Exe = 'python3'; Args = @() }
)
foreach ($k in $kandidaten) {
    if (-not (Hat-Befehl $k.Exe)) { continue }
    try {
        $alt = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $ok = & $k.Exe @($k.Args) -c 'import sys; print(1 if sys.version_info >= (3, 11) else 0)' 2>$null
        $ErrorActionPreference = $alt
        if ("$ok".Trim() -eq '1') { $Python = $k; break }
    } catch { $ErrorActionPreference = 'Stop' }
}
if (-not $Python) {
    Fehler 'Python 3.11 oder neuer fehlt. Bitte von https://www.python.org/downloads/ installieren (Haken "Add python.exe to PATH" setzen) und dieses Skript erneut starten.'
}
if (-not (Hat-Befehl 'npm')) {
    Fehler 'Node.js fehlt. Bitte die LTS-Version von https://nodejs.org installieren und dieses Skript erneut starten.'
}

# Laeuft noch ein alter Crawler, wuerde sonst weiter die alte Version antworten - beenden.
$alte = @()
if (Hat-Befehl 'Get-NetTCPConnection') {
    $alte = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}
if ($alte.Count -gt 0) {
    if (Crawler-Laeuft) {
        Schritt 'Beende den noch laufenden Crawler, damit die neueste Version startet'
        foreach ($c in $alte) { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    } else {
        Fehler "Port $Port ist von einem anderen Programm belegt. Bitte dieses Programm beenden und den Crawler erneut starten."
    }
}

# --- Updates holen (optional) -------------------------------------------------------------
if ((Test-Path (Join-Path $Projekt '.git'))) {
    if (Hat-Befehl 'git') {
        Schritt 'Suche nach Updates'
        $vorher = (Get-FileHash $PSCommandPath).Hash
        $null = Ausfuehren 'git' @('pull', '--ff-only')
        # Hat das Update dieses Skript selbst geaendert, einmal mit der neuen Fassung neu starten.
        if (-not $env:CRAWLER_SKRIPT_NEU_GESTARTET -and (Get-FileHash $PSCommandPath).Hash -ne $vorher) {
            $env:CRAWLER_SKRIPT_NEU_GESTARTET = '1'
            $host_exe = (Get-Process -Id $PID).Path
            & $host_exe -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
            exit $LASTEXITCODE
        }
    } else {
        Hinweis 'Git ist nicht installiert - automatische Updates sind aus (siehe docs/ANLEITUNG-kollegen.md).'
    }
}

# --- Backend einrichten -------------------------------------------------------------------
$null = New-Item -ItemType Directory -Force -Path (Join-Path $Backend 'data')
$Venv = Join-Path $Backend '.venv'
$VenvPython = Join-Path (Join-Path $Venv 'Scripts') 'python.exe'

if (-not (Test-Path $VenvPython)) {
    Schritt 'Erstmalige Einrichtung: Python-Umgebung anlegen'
    Push-Location $Backend
    $code = Ausfuehren $Python.Exe (@($Python.Args) + @('-m', 'venv', '.venv'))
    Pop-Location
    if ($code -ne 0) { Fehler 'Die Python-Umgebung konnte nicht angelegt werden.' }
}

$reqStand = (Get-FileHash (Join-Path $Backend 'requirements.txt')).Hash
$stempel = Join-Path $Venv '.installiert'
if (-not (Test-Path $stempel) -or ((Get-Content $stempel -Raw).Trim() -ne $reqStand)) {
    Schritt 'Python-Pakete installieren (dauert beim ersten Mal ein paar Minuten)'
    $null = Ausfuehren $VenvPython @('-m', 'pip', 'install', '--upgrade', 'pip', '-q')
    $code = Ausfuehren $VenvPython @('-m', 'pip', 'install', '-r', (Join-Path $Backend 'requirements.txt'), '-q')
    if ($code -ne 0) { Fehler 'Die Python-Pakete konnten nicht installiert werden (Internetverbindung?).' }
    Set-Content -Path $stempel -Value $reqStand
    Remove-Item (Join-Path $Venv '.browser-ok'), (Join-Path $Venv '.browser-uebersprungen') -ErrorAction SilentlyContinue
}

# Browser fuer das DB Bieterportal: Chrome oder Edge reichen (Edge ist unter Windows immer da),
# sonst genau ein Download-Versuch von Playwrights Chromium.
$browserOk = Join-Path $Venv '.browser-ok'
$browserAus = Join-Path $Venv '.browser-uebersprungen'
if (-not (Test-Path $browserOk) -and -not (Test-Path $browserAus)) {
    # Basisordner koennen fehlen (z. B. ProgramFiles(x86) auf 32-Bit-Systemen) - nur vorhandene nutzen.
    $basen = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LocalAppData) | Where-Object { $_ }
    $unterpfade = @('Google\Chrome\Application\chrome.exe', 'Microsoft\Edge\Application\msedge.exe')
    $browser = @()
    foreach ($basis in $basen) {
        foreach ($unter in $unterpfade) {
            $kandidat = Join-Path $basis $unter
            if (Test-Path $kandidat) { $browser += $kandidat }
        }
    }
    if ($browser) {
        Write-Host 'Chrome/Edge gefunden - wird fuer das DB Bieterportal genutzt, kein Download noetig.'
        Set-Content -Path $browserOk -Value 'ok'
    } else {
        Schritt 'Headless-Browser fuer das DB Bieterportal installieren'
        $env:PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT = '180000'
        $code = Ausfuehren $VenvPython @('-m', 'playwright', 'install', 'chromium')
        if ($code -eq 0) { Set-Content -Path $browserOk -Value 'ok' }
        else {
            Set-Content -Path $browserAus -Value 'uebersprungen'
            Hinweis 'Hinweis: Browser-Download fehlgeschlagen - nur das DB Bieterportal ist betroffen, alle anderen Portale funktionieren.'
        }
    }
}

$envDatei = Join-Path $Backend '.env'
if (-not (Test-Path $envDatei)) {
    $zeilen = @(
        '# Kein automatisches Hintergrund-Crawling ausser dem taeglichen Lauf (Standard 07:00, nur wenn der Rechner an ist).',
        'CRAWLER_SCHEDULER_ENABLED=false',
        '# Crawler Kevin laeuft kostenlos ueber Ollama (https://ollama.com). Optional stattdessen Claude',
        '# (kostenpflichtig): Raute entfernen und den eigenen Schluessel eintragen:',
        '# CRAWLER_ANTHROPIC_API_KEY=sk-ant-...',
        '# Anderes lokales Modell erzwingen (Standard: qwen3:8b, bei wenig Arbeitsspeicher qwen3:4b):',
        '# CRAWLER_OLLAMA_MODEL=qwen3:8b',
        '# Fuer Zugriff von anderen Geraeten im selben Netz (ohne Passwortschutz!):',
        '# CRAWLER_HOST=0.0.0.0'
    )
    Set-Content -Path $envDatei -Value $zeilen -Encoding ASCII
}

# --- Frontend bauen (nur wenn sich der Frontend-Code geaendert hat) -------------------------
$staticIndex = Join-Path (Join-Path $Backend 'static') 'index.html'
$buildStempel = Join-Path $Frontend '.build-stand'
$feDateien = @()
foreach ($ordner in @('src', 'public')) {
    $pfad = Join-Path $Frontend $ordner
    if (Test-Path $pfad) { $feDateien += @(Get-ChildItem -Path $pfad -Recurse -File) }
}
foreach ($name in @('index.html', 'package.json', 'package-lock.json', 'vite.config.ts')) {
    $pfad = Join-Path $Frontend $name
    if (Test-Path $pfad) { $feDateien += @(Get-Item $pfad) }
}
$feStand = Text-Hash ((($feDateien | Sort-Object FullName | ForEach-Object { (Get-FileHash $_.FullName -Algorithm SHA1).Hash }) -join ''))
if (-not (Test-Path $staticIndex) -or -not (Test-Path $buildStempel) -or ((Get-Content $buildStempel -Raw).Trim() -ne $feStand)) {
    Schritt 'Oberflaeche bauen'
    Push-Location $Frontend
    $env:VITE_API_BASE_URL = '/api'
    $code = Ausfuehren 'npm' @('ci', '--no-audit', '--no-fund', '--loglevel=error')
    if ($code -eq 0) { $code = Ausfuehren 'npm' @('run', 'build') }
    Pop-Location
    if ($code -ne 0) { Fehler 'Die Oberflaeche konnte nicht gebaut werden (Node.js installiert? Internetverbindung?).' }
    $static = Join-Path $Backend 'static'
    if (Test-Path $static) { Remove-Item -Recurse -Force $static }
    Copy-Item -Recurse (Join-Path $Frontend 'dist') $static
    Set-Content -Path $buildStempel -Value $feStand
}

# --- Crawler Kevin: kostenloses lokales Sprachmodell ueber Ollama ---------------------------
if (-not (Env-Wert 'CRAWLER_ANTHROPIC_API_KEY')) {
    $ollama = $null
    if (Hat-Befehl 'ollama') { $ollama = 'ollama' }
    else {
        if ($env:LocalAppData) {
            $pfadOllama = Join-Path $env:LocalAppData 'Programs\Ollama\ollama.exe'
            if (Test-Path $pfadOllama) { $ollama = $pfadOllama }
        }
    }
    if (-not $ollama) {
        Hinweis 'Hinweis: Fuer Crawler Kevin (kostenlos) bitte Ollama von https://ollama.com installieren und den Crawler danach neu starten. Alles andere funktioniert auch ohne.'
    } else {
        $modell = Env-Wert 'CRAWLER_OLLAMA_MODEL'
        if (-not $modell) {
            $ramGb = 0
            try { $ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB) } catch { }
            if ($ramGb -ge 15) { $modell = 'qwen3:8b' } else { $modell = 'qwen3:4b' }
            $env:CRAWLER_OLLAMA_MODEL = $modell
        }
        $ollamaLaeuft = $false
        try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/version' -UseBasicParsing -TimeoutSec 2; $ollamaLaeuft = $true } catch { }
        if (-not $ollamaLaeuft) {
            Schritt 'Ollama starten'
            Start-Process -FilePath $ollama -ArgumentList 'serve' -WindowStyle Hidden
            for ($i = 0; $i -lt 30 -and -not $ollamaLaeuft; $i++) {
                Start-Sleep -Seconds 1
                try { $null = Invoke-WebRequest -Uri 'http://localhost:11434/api/version' -UseBasicParsing -TimeoutSec 2; $ollamaLaeuft = $true } catch { }
            }
        }
        if ($ollamaLaeuft) {
            $vorhanden = @(& $ollama list 2>$null | Select-Object -Skip 1 | ForEach-Object { ($_ -split '\s+')[0] })
            if ($vorhanden -notcontains $modell) {
                Schritt "Sprachmodell $modell fuer Crawler Kevin herunterladen (einmalig, einige GB)"
                $code = Ausfuehren $ollama @('pull', $modell)
                if ($code -ne 0) { Hinweis 'Hinweis: Download fehlgeschlagen - wird beim naechsten Start erneut versucht.' }
            }
            # Modell schon jetzt im Hintergrund in den Speicher laden.
            $null = Start-Job -ScriptBlock {
                param($m)
                try {
                    Invoke-RestMethod -Method Post -Uri 'http://localhost:11434/api/generate' -ContentType 'application/json' `
                        -Body (@{ model = $m; keep_alive = '60m' } | ConvertTo-Json) -TimeoutSec 600 | Out-Null
                } catch { }
            } -ArgumentList $modell
            Write-Host "Crawler Kevin nutzt das lokale Modell $modell (kostenlos)."
        } else {
            Hinweis 'Hinweis: Ollama liess sich nicht starten - bitte die Ollama-App einmal von Hand oeffnen.'
        }
    }
}

# --- Starten ------------------------------------------------------------------------------
$hostAdresse = Env-Wert 'CRAWLER_HOST'
if (-not $hostAdresse) { $hostAdresse = '127.0.0.1' }
Schritt "Crawler laeuft auf $Url"
if ($hostAdresse -ne '127.0.0.1') {
    try {
        $ip = (Get-NetIPAddress -AddressFamily IPv4 -ErrorAction Stop |
            Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' } |
            Select-Object -First 1).IPAddress
        if ($ip) { Write-Host "Andere Geraete im selben Netz: http://${ip}:$Port" -ForegroundColor White }
    } catch { }
}
Write-Host 'Zum Beenden dieses Fenster schliessen oder Strg+C druecken.'

$null = Start-Job -ScriptBlock {
    param($u)
    for ($i = 0; $i -lt 60; $i++) {
        try { $null = Invoke-WebRequest -Uri "$u/api/health" -UseBasicParsing -TimeoutSec 2; Start-Process $u; return } catch { Start-Sleep -Seconds 1 }
    }
} -ArgumentList $Url

Set-Location $Backend
& $VenvPython -m uvicorn app.main:app --host $hostAdresse --port $Port
if ($LASTEXITCODE -ne 0) {
    Fehler "Der Crawler wurde mit einem Fehler beendet (Code $LASTEXITCODE). Meldung oben bitte weitergeben."
}
