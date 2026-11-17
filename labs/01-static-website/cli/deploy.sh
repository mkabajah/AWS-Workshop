#!/usr/bin/env bash
# Lab 01 · Upload the website and clear the CloudFront cache.
#
#   ./labs/01-static-website/cli/deploy.sh <bucket-name> <distribution-id>
#
# Works with a bucket made in the console or by the CloudFormation template.
# With the template, read both values from its Outputs:
#   aws cloudformation describe-stacks --stack-name lab01-static-site --query "Stacks[0].Outputs" --output table
set -euo pipefail

BUCKET="${1:?usage: deploy.sh <bucket-name> <distribution-id>}"
DISTRIBUTION_ID="${2:?usage: deploy.sh <bucket-name> <distribution-id>}"
SITE_DIR="$(cd "$(dirname "$0")/../../../site" && pwd)"

echo "Deploying as: $(aws sts get-caller-identity --query Arn --output text)"

echo "1/2 Uploading $SITE_DIR → s3://$BUCKET (only changed files)"
aws s3 sync "$SITE_DIR" "s3://$BUCKET" --delete --exclude ".DS_Store"

echo "2/2 Clearing the CloudFront cache"
aws cloudfront create-invalidation --distribution-id "$DISTRIBUTION_ID" --paths "/*" \
  --query "Invalidation.[Id,Status]" --output text

echo "Done. Refresh the site in about a minute."
