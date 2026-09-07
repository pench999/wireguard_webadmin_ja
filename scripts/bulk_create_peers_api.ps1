param(
    [Parameter(Mandatory = $true)]
    [string]$BaseUrl,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [string]$Instance = "wg0",

    [int]$Count = 70,

    [string]$NamePrefix = "peer-",

    [int]$Start = 1,

    [string]$OutCsv = ".\created_peers.csv",

    [switch]$ReloadEach,

    [switch]$WhatIfOnly
)

$ErrorActionPreference = "Stop"

if ($Count -lt 1) {
    throw "Count must be 1 or greater."
}

if ($Start -lt 0) {
    throw "Start must be 0 or greater."
}

$apiUrl = $BaseUrl.TrimEnd("/") + "/api/v2/manage_peer/"
$headers = @{
    token = $Token
}

$created = New-Object System.Collections.Generic.List[object]

for ($i = 0; $i -lt $Count; $i++) {
    $number = $Start + $i
    $name = "{0}{1:D3}" -f $NamePrefix, $number
    $body = @{
        instance = $Instance
        name = $name
        skip_reload = -not $ReloadEach.IsPresent
    }

    if ($WhatIfOnly) {
        Write-Host "Would create $name on $Instance"
        continue
    }

    try {
        $response = Invoke-RestMethod `
            -Method Post `
            -Uri $apiUrl `
            -Headers $headers `
            -ContentType "application/json" `
            -Body ($body | ConvertTo-Json -Depth 5)

        $row = [pscustomobject]@{
            name = $name
            peer_uuid = $response.peer_uuid
            public_key = $response.public_key
            main_addresses = ($response.main_addresses -join ", ")
            reload_success = $response.reload.success
            reload_message = $response.reload.message
        }
        $created.Add($row) | Out-Null
        Write-Host "Created $name $($response.peer_uuid) $($row.main_addresses)"
    }
    catch {
        if ($created.Count -gt 0) {
            $created | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $OutCsv
        }
        throw "Failed while creating $name. $($_.Exception.Message)"
    }
}

if (-not $WhatIfOnly) {
    $created | Export-Csv -NoTypeInformation -Encoding UTF8 -Path $OutCsv
    Write-Host "Created $($created.Count) peers. CSV: $OutCsv"

    if (-not $ReloadEach) {
        Write-Host "Reload was skipped for each request. Export/reload once from the GUI after checking the created peers."
    }
}
