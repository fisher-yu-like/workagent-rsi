param(
    [Parameter(Mandatory = $true)][string]$Root,
    [Parameter(Mandatory = $true)][string]$OutputJson
)

$ErrorActionPreference = "Stop"
$apps = @{}
$versions = @{}
$rows = @()
$files = Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object { $_.Extension.ToLowerInvariant() -in @('.docx', '.xlsx', '.pptx') }

function Get-App([string]$extension) {
    if ($apps.ContainsKey($extension)) { return $apps[$extension] }
    switch ($extension) {
        '.docx' {
            $app = New-Object -ComObject Word.Application
            $app.Visible = $false
            $app.DisplayAlerts = 0
            $app.AutomationSecurity = 3
        }
        '.xlsx' {
            $app = New-Object -ComObject Excel.Application
            $app.Visible = $false
            $app.DisplayAlerts = $false
            $app.AutomationSecurity = 3
        }
        '.pptx' {
            $app = New-Object -ComObject PowerPoint.Application
        }
        default { throw "Unsupported extension: $extension" }
    }
    $apps[$extension] = $app
    $versions[$extension] = [string]$app.Version
    return $app
}

try {
    foreach ($file in $files) {
        $app = $null
        $document = $null
        $opened = $false
        $errorMessage = $null
        try {
            $app = Get-App $file.Extension.ToLowerInvariant()
            switch ($file.Extension.ToLowerInvariant()) {
                '.docx' { $document = $app.Documents.Open($file.FullName, $false, $true, $false) }
                '.xlsx' { $document = $app.Workbooks.Open($file.FullName, $null, $true) }
                '.pptx' { $document = $app.Presentations.Open($file.FullName, $true, $true, $false) }
            }
            $opened = $true
        } catch {
            $errorMessage = $_.Exception.Message
        } finally {
            if ($document -ne $null) {
                try { $document.Close($false) } catch { try { $document.Close() } catch {} }
                try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($document) | Out-Null } catch {}
            }
        }
        $rows += [ordered]@{ file = $file.FullName; extension = $file.Extension.ToLowerInvariant(); opened = $opened; error = $errorMessage }
    }
} finally {
    foreach ($app in $apps.Values) {
        try { $app.Quit() } catch {}
        try { [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null } catch {}
    }
}

$report = [ordered]@{
    office_versions = [ordered]@{
        word = $versions['.docx']
        excel = $versions['.xlsx']
        powerpoint = $versions['.pptx']
    }
    file_count = $rows.Count
    opened_count = @($rows | Where-Object opened).Count
    failures = @($rows | Where-Object { -not $_.opened })
    rows = $rows
}
($report | ConvertTo-Json -Depth 8) | Set-Content -LiteralPath $OutputJson -Encoding utf8
if ($report.failures.Count -gt 0) { exit 1 }
