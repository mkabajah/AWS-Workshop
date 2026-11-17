#!/usr/bin/env bash
# Builds function.zip (code + the pg driver) to upload in the Lambda console.
#   ./scripts/package.sh
set -euo pipefail
cd "$(dirname "$0")/../src"
rm -rf node_modules function.zip
npm install --omit=dev --no-audit --no-fund
zip -qr ../function.zip index.mjs package.json node_modules
echo "Created $(cd .. && pwd)/function.zip ($(du -h ../function.zip | cut -f1)). Upload it in Lambda → Code → Upload from → .zip file"
