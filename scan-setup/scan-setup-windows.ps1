<#
  scan-setup-windows.ps1
  Interaktives Setup fuer 3D-Scan (Photogrammetrie) auf dem RTX-Rechner (Windows).
  Installiert: Meshroom (Photogrammetrie, Open Source), Blender (Mesh aufbereiten),
  PrusaSlicer (drucken). Legt eine Ordnerstruktur an und sagt am Ende, was zu tun ist.

  Start (einmalig, Rechtsklick PowerShell "als Administrator" ODER normal):
      powershell -ExecutionPolicy Bypass -File .\scan-setup-windows.ps1
#>

$ErrorActionPreference = "Stop"
function Say($m){ Write-Host ""; Write-Host ">>> $m" -ForegroundColor Cyan }
function Ask($m){ (Read-Host "$m [J/n]") -notmatch '^[nN]' }

Write-Host "=== 3D-Scan Setup (Windows) ===" -ForegroundColor Green

# --- 1. NVIDIA pruefen ---
Say "Pruefe NVIDIA-Grafikkarte (noetig fuer Meshroom)..."
try {
  $smi = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
  if ($smi) { Write-Host "OK: $smi" -ForegroundColor Green }
  else { throw }
} catch {
  Write-Host "WARNUNG: keine NVIDIA erkannt. Meshroom braucht NVIDIA/CUDA." -ForegroundColor Yellow
  Write-Host "Ohne NVIDIA lieber Handy-Cloud-Apps (KIRI Engine/Polycam) nutzen." -ForegroundColor Yellow
  if (-not (Ask "Trotzdem weitermachen?")) { exit }
}

# --- 2. Ordnerstruktur ---
$base = Join-Path $HOME "3DScan"
"Fotos","Projekte","Export","Tools" | ForEach-Object {
  New-Item -ItemType Directory -Force -Path (Join-Path $base $_) | Out-Null
}
Say "Arbeitsordner angelegt: $base  (Fotos / Projekte / Export / Tools)"

# --- 3. Blender + PrusaSlicer via winget ---
$winget = Get-Command winget -ErrorAction SilentlyContinue
if ($winget) {
  if (Ask "Blender installieren (Mesh aufbereiten)?") {
    Say "Installiere Blender..."; winget install -e --id BlenderFoundation.Blender --accept-package-agreements --accept-source-agreements
  }
  if (Ask "PrusaSlicer installieren (fuer den Druck)?") {
    Say "Installiere PrusaSlicer..."; winget install -e --id Prusa3D.PrusaSlicer --accept-package-agreements --accept-source-agreements
  }
} else {
  Write-Host "winget nicht gefunden - Blender/PrusaSlicer bitte manuell: blender.org / prusa3d.com" -ForegroundColor Yellow
}

# --- 4. Meshroom (neueste Version von GitHub) ---
if (Ask "Meshroom herunterladen & entpacken (~1.5 GB)?") {
  Say "Suche neueste Meshroom-Version..."
  $tools = Join-Path $base "Tools"
  try {
    $rel = Invoke-RestMethod "https://api.github.com/repos/alicevision/Meshroom/releases/latest" -Headers @{ "User-Agent"="scan-setup" }
    $asset = $rel.assets | Where-Object { $_.name -match "win.*\.zip$" } | Select-Object -First 1
    $url = $asset.browser_download_url
  } catch { $url = "https://github.com/alicevision/Meshroom/releases/download/v2023.3.0/Meshroom-2023.3.0-win64.zip" }
  $zip = Join-Path $tools "Meshroom.zip"
  Say "Lade: $url"
  Invoke-WebRequest -Uri $url -OutFile $zip
  Say "Entpacke nach $tools ..."
  Expand-Archive -Path $zip -DestinationPath $tools -Force
  Remove-Item $zip
  $exe = Get-ChildItem -Path $tools -Recurse -Filter "Meshroom.exe" | Select-Object -First 1
  if ($exe) { Write-Host "Meshroom bereit: $($exe.FullName)" -ForegroundColor Green }
}

# --- 5. Anleitung ---
Say "FERTIG. So machst du deinen ersten Scan:"
@"
1) FOTOS MACHEN (Handy reicht):
   - kleines Objekt: 40-80 Fotos rundherum, in 2-3 Hoehen-Ringen
   - gleichmaessiges Licht (kein harter Schatten), 70-80% Ueberlappung, scharf
   - Fotos nach:  $base\Fotos\<meinobjekt>\

2) MESHROOM:
   - Meshroom.exe starten (in $base\Tools\...)
   - alle Fotos ins linke Fenster ziehen  ->  oben auf "Start"
   - warten (RTX rechnet) -> fertiges Modell erscheint; Ergebnis liegt in
     MeshroomCache\Texturing\...  (texturedMesh.obj) -> nach $base\Export kopieren

3) AUFBEREITEN (Blender):
   - OBJ importieren -> Boden/Muell wegschneiden -> ggf. aushoehlen/vereinfachen
   - skalieren -> als STL exportieren

4) DRUCKEN:
   - STL in PrusaSlicer -> Supports an -> Slice -> drucken

TIPP: Erst ein kleines Testobjekt. Grosse Gebaeude: 200-500 Fotos, 80% Ueberlappung.
Fuer die Kastelburg: Mini-Drohne <250g + vorher dipul.de pruefen.
"@ | Write-Host
