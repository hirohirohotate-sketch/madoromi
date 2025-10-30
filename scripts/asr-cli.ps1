param(
  [Parameter(ValueFromRemainingArguments = $true)][string[]]$InputPaths,
  [ValidateSet("srt","json")][string]$Format = "srt",
  [string]$Lang = "ja",
  [string]$Endpoint = "http://127.0.0.1:8080/asr",
  [string]$ApiKey = $env:LG_API_KEY  # 必要なら環境変数でAPIキー渡す
)

Add-Type -AssemblyName System.Net.Http
$http = [System.Net.Http.HttpClient]::new()
if ($ApiKey) {
  $http.DefaultRequestHeaders.Add("X-API-Key", $ApiKey)
}

foreach ($p in $InputPaths) {
  $file = Get-Item $p -ErrorAction SilentlyContinue
  if (-not $file) {
    Write-Host "not found: $p"
    continue
  }

  $content = [System.Net.Http.MultipartFormDataContent]::new()
  $fs = [System.IO.File]::OpenRead($file.FullName)
  $sc = [System.Net.Http.StreamContent]::new($fs)
  $sc.Headers.ContentType = [System.Net.Http.Headers.MediaTypeHeaderValue]::Parse("application/octet-stream")
  $content.Add($sc, "file", $file.Name)
  $content.Add([System.Net.Http.StringContent]::new($Format), "format")
  $content.Add([System.Net.Http.StringContent]::new($Lang), "lang")

  try {
    $resp = $http.PostAsync($Endpoint, $content).GetAwaiter().GetResult()
    $bytes = $resp.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult()
    if (-not $resp.IsSuccessStatusCode) {
      $msg = [System.Text.Encoding]::UTF8.GetString($bytes)
      Write-Host "ERROR $($resp.StatusCode): $msg"
      continue
    }
    $out = if ($Format -eq "srt") {
      [IO.Path]::ChangeExtension($file.FullName,".srt")
    } else {
      [IO.Path]::ChangeExtension($file.FullName,".json")
    }
    [IO.File]::WriteAllBytes($out, $bytes)
    Write-Host "saved: $out"
  } finally {
    $fs.Dispose()
    $sc.Dispose()
    $content.Dispose()
  }
}

$http.Dispose()