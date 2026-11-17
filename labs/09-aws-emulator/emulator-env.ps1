# Lab 09 · Point this PowerShell window at AWS Emulator (Windows).
#
#   . .\labs\09-aws-emulator\emulator-env.ps1           # port 9297
#   . .\labs\09-aws-emulator\emulator-env.ps1 9298      # a second emulator
#
# Note the leading dot and space: it runs the script in this window.

param([int]$Port = 9297)
$E = "$env:USERPROFILE\.aws\emulator\$Port"

$env:AWS_ENDPOINT_URL = "https://127.0.0.1:$Port"
$env:AWS_SHARED_CREDENTIALS_FILE = "$E\emulator_credentials"
$env:AWS_CONFIG_FILE = "$E\config"
$env:AWS_CA_BUNDLE = "$E\ca.pem"
$env:AWS_EC2_METADATA_DISABLED = "true"
$env:AWS_DISABLE_HOST_PREFIX_INJECTION = "true"
$env:AWS_REGION = "us-east-1"
$env:AWS_DEFAULT_REGION = "us-east-1"

# Make sure real credentials can't be used by accident.
Remove-Item Env:AWS_ACCESS_KEY_ID, Env:AWS_SECRET_ACCESS_KEY, Env:AWS_SESSION_TOKEN, Env:AWS_PROFILE -ErrorAction SilentlyContinue

if (-not (Test-Path "$E\emulator_credentials")) {
  Write-Warning "$E\emulator_credentials not found. Is the emulator running on port $Port?"
}
Write-Host "This window now talks to AWS Emulator at $env:AWS_ENDPOINT_URL"
Write-Host "Check:  aws sts get-caller-identity   (Account must be 000000000000)"
