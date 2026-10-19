$ErrorActionPreference = 'Stop'

$server = 'root@45.142.36.78'
$projectDir = $PSScriptRoot
$sshKey = Join-Path $env:USERPROFILE '.ssh\santehgo_deploy_ed25519'
$archive = Join-Path ([System.IO.Path]::GetTempPath()) 'santehgo-update.tar.gz'
$remoteArchive = '/tmp/santehgo-update.tar.gz'

if (-not (Test-Path -LiteralPath $sshKey)) {
    throw "SSH key not found: $sshKey"
}

Write-Host '1/3  Packaging changed project files...'

try {
    & tar.exe -czf $archive `
        --exclude=.git `
        --exclude=.venv `
        --exclude=.artifact-node `
        --exclude=outputs `
        --exclude=__pycache__ `
        --exclude='*.pyc' `
        --exclude=.env `
        --exclude=db.sqlite3 `
        --exclude=deploy-data.json `
        --exclude=media `
        --exclude=staticfiles `
        --exclude='*.log' `
        -C $projectDir .

    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to create deployment archive.'
    }

    Write-Host '2/3  Uploading files...'
    & scp.exe -i $sshKey -o StrictHostKeyChecking=accept-new $archive "${server}:$remoteArchive"
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to upload deployment archive.'
    }

    Write-Host '3/3  Rebuilding and restarting containers...'
    $remoteCommand = @"
set -eu
tar -xzf $remoteArchive -C /opt/santehgo
rm -f $remoteArchive
cd /opt/santehgo
docker compose up -d --build --remove-orphans
docker compose ps
"@

    & ssh.exe -i $sshKey -o StrictHostKeyChecking=accept-new $server $remoteCommand
    if ($LASTEXITCODE -ne 0) {
        throw 'Deployment failed on the server.'
    }

    Write-Host ''
    Write-Host 'Deployment completed: https://xn--80agf5ahnjz.xn--p1ai' -ForegroundColor Green
}
finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}
