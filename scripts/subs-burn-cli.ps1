param(
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$Paths,
  [int]$FontSize = 30,
  [string]$Endpoint = "http://127.0.0.1:8080/subs/burn",
  [string]$ApiKey = $env:LG_API_KEY
)

if ($Paths.Count -lt 2) {
  Write-Host "動画とSRTを両方ドロップしてください"
  exit 1
}

$video = $Paths | Where-Object { $_ -match "\.(mp4|mov|mkv|webm)$" } | Select-Object -First 1
$srt   = $Paths | Where-Object { $_ -match "\.srt$" } | Select-Object -First 1

if (-not $video -or -not $srt) {
  Write-Host "動画(.mp4等)とSRT(.srt)が必要です"
  exit 1
}

Add-Type -AssemblyName System.Net.Http
$http = [System.Net.Http.HttpClient]::new()
if ($ApiKey) {
  $http.DefaultRequestHeaders.Add("X-API-Key", $ApiKey)
}

$content = [System.Net.Http.MultipartFormDataContent]::new()
$vf = [System.IO.File]::OpenRead($video)
$sf = [System.IO.File]::OpenRead($srt)
$vc = [System.Net.Http.StreamContent]::new($vf)
$vc.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("video/mp4")
$sc = [System.Net.Http.StreamContent]::new($sf)
$sc.Headers.ContentType=[System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("text/plain")

$content.Add($vc,"video",[IO.Path]::GetFileName($video))
$content.Add($sc,"srt",[IO.Path]::GetFileName($srt))
$content.Add([System.Net.Http.StringContent]::new([string]$FontSize),"font_size")

$out = [IO.Path]::Combine([IO.Path]::GetDirectoryName($video),"with_subs.mp4")

try {
  $resp = $http.PostAsync($Endpoint,$content).GetAwaiter().GetResult()
  $bytes = $resp.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
  if (-not $resp.IsSuccessStatusCode) {
    $msg = [System.Text.Encoding]::UTF8.GetString($bytes)
    Write-Host "ERROR $($resp.StatusCode): $msg"
    exit 1
  }
  [IO.File]::WriteAllBytes($out,$bytes)
  Write-Host "saved: $out"
} finally {
  $vf.Dispose()
  $sf.Dispose()
  $vc.Dispose()
  $sc.Dispose()
  $content.Dispose()
  $http.Dispose()
}