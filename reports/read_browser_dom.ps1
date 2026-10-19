param(
    [Parameter(Mandatory=$true)][string]$Expression,
    [string]$OutputFile = '',
    [int]$Port = 49871
)
$ErrorActionPreference = 'Stop'
$tabs = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/json/list" -TimeoutSec 5
$targets = @(foreach ($tab in $tabs) {
    if ($tab.type -eq 'page' -and ([uri]$tab.url).Host -eq 'www.zhipin.com') { $tab }
})
if ($targets.Count -ne 1) { throw 'Expected exactly one BOSS page; no page selected.' }
$socket = [System.Net.WebSockets.ClientWebSocket]::new()
$cancel = [System.Threading.CancellationTokenSource]::new(20000)
try {
    $socket.ConnectAsync([uri]$targets[0].webSocketDebuggerUrl, $cancel.Token).GetAwaiter().GetResult()
    $request = @{id=1;method='Runtime.evaluate';params=@{
        expression=$Expression;returnByValue=$true;awaitPromise=$false
    }} | ConvertTo-Json -Depth 8 -Compress
    $bytes = [Text.Encoding]::UTF8.GetBytes($request)
    $socket.SendAsync([ArraySegment[byte]]::new($bytes), [System.Net.WebSockets.WebSocketMessageType]::Text, $true, $cancel.Token).GetAwaiter().GetResult()
    do {
        $buffer = New-Object byte[] 65536
        $stream = [IO.MemoryStream]::new()
        try {
            do {
                $received = $socket.ReceiveAsync([ArraySegment[byte]]::new($buffer), $cancel.Token).GetAwaiter().GetResult()
                if ($received.MessageType -eq [System.Net.WebSockets.WebSocketMessageType]::Close) { throw 'Browser disconnected.' }
                $stream.Write($buffer, 0, $received.Count)
            } while (-not $received.EndOfMessage)
            $reply = [Text.Encoding]::UTF8.GetString($stream.ToArray()) | ConvertFrom-Json
        } finally { $stream.Dispose() }
    } while ($reply.id -ne 1)
    if ($reply.error) { throw ($reply.error | ConvertTo-Json -Compress) }
    if ($reply.result.exceptionDetails) { throw ($reply.result.exceptionDetails | ConvertTo-Json -Depth 8 -Compress) }
    $value = $reply.result.result.value
    if ($OutputFile) {
        $absolute = [IO.Path]::GetFullPath($OutputFile)
        if (-not $absolute.StartsWith('E:\automatic_recruitment\reports\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must stay in the reports directory.' }
        [IO.File]::WriteAllText($absolute, [string]$value, [Text.UTF8Encoding]::new($false))
        Write-Output ('Saved: ' + $absolute)
    } else { Write-Output $value }
} finally { $socket.Dispose(); $cancel.Dispose() }
