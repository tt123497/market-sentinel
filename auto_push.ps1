# Auto push to GitHub - retries every 30 min until success
$env:Path = "D:\Tools\GitHub CLI;D:\Tools\Git\bin;" + $env:Path

$token = gh auth token 2>$null
if (-not $token) { exit }

Set-Location D:\projects\market-dashboard

git remote remove origin 2>$null
git remote add origin "https://oauth2:$token@github.com/tt123497/market-sentinel.git"
git add data.json index.html -A 2>$null
git commit --allow-empty -m "auto sync" 2>$null

$result = git push -u origin master --force 2>&1
if ($LASTEXITCODE -eq 0) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$ts - PUSH SUCCESS" | Out-File "D:\projects\market-dashboard\push_log.txt" -Append
    # Enable Pages
    $body = @{source=@{branch="master";path="/"}} | ConvertTo-Json
    Invoke-RestMethod -Uri "https://api.github.com/repos/tt123497/market-sentinel/pages" -Method Post -Headers @{Authorization="Bearer $token"} -Body $body -ContentType "application/json" -TimeoutSec 15 | Out-Null
    # Disable the scheduled task after success
    schtasks /delete /tn "GitHubAutoPush" /f 2>$null
} else {
    "$ts - retrying..." | Out-File "D:\projects\market-dashboard\push_log.txt" -Append
}
