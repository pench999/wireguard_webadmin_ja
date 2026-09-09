param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$SessionId,

    [Parameter(Mandatory = $true)]
    [string]$InputCsv,

    [string]$OutDir = ".\peer_assets",

    [switch]$ConfigOnly,

    [switch]$QrOnly,

    [switch]$Zip
)

$ErrorActionPreference = "Stop"

if ($ConfigOnly -and $QrOnly) {
    throw "ConfigOnly and QrOnly cannot be used together."
}

if (-not (Test-Path -Path $InputCsv)) {
    throw "InputCsv not found: $InputCsv"
}

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$base = $BaseUrl.TrimEnd("/")
$cookieHeader = "sessionid=$SessionId"
$rows = Import-Csv -Path $InputCsv

if (-not $rows -or -not ($rows[0].PSObject.Properties.Name -contains "peer_uuid")) {
    throw "InputCsv must contain a peer_uuid column. Use the CSV produced by bulk_create_peers_api.ps1."
}

function ConvertTo-SafeFileName {
    param([string]$Value)

    $safe = $Value -replace '[\\/:*?"<>|]', "_"
    $safe = $safe.Trim()
    if (-not $safe) {
        return "peer"
    }
    return $safe
}

foreach ($row in $rows) {
    $peerUuid = $row.peer_uuid
    if (-not $peerUuid) {
        continue
    }

    $peerName = $row.name
    if (-not $peerName) {
        $peerName = $peerUuid
    }

    $fileBase = ConvertTo-SafeFileName -Value $peerName

    if (-not $QrOnly) {
        $confUrl = "$base/tools/download_peer_config/?uuid=$peerUuid&format=conf"
        $confPath = Join-Path $OutDir "$fileBase.conf"
        Invoke-WebRequest -Uri $confUrl -Headers @{ Cookie = $cookieHeader } -OutFile $confPath
        Write-Host "Downloaded config: $confPath"
    }

    if (-not $ConfigOnly) {
        $qrUrl = "$base/tools/download_peer_config/?uuid=$peerUuid&format=qrcode"
        $qrPath = Join-Path $OutDir "$fileBase.png"
        Invoke-WebRequest -Uri $qrUrl -Headers @{ Cookie = $cookieHeader } -OutFile $qrPath
        Write-Host "Downloaded QR: $qrPath"
    }
}

if ($Zip) {
    $zipPath = "$OutDir.zip"
    if (Test-Path -Path $zipPath) {
        Remove-Item -Path $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $OutDir "*") -DestinationPath $zipPath
    Write-Host "Created zip: $zipPath"
}
