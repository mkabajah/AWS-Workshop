#!/usr/bin/env bash
# Deploy any lab's CloudFormation template from the terminal.
#
#   ./scripts/deploy-cfn.sh <template.yaml> <stack-name> [Key=Value ...]
#
# Examples:
#   ./scripts/deploy-cfn.sh labs/02-lambda-basics/cloudformation/lambda-basics.yaml lab02-hello
#   ./scripts/deploy-cfn.sh labs/04-event-triggers/cloudformation/event-triggers.yaml lab04-triggers NotificationEmail=you@example.com
#
# What it does:
#   1. makes sure an S3 bucket exists for code packages (once per account and Region)
#   2. "aws cloudformation package" zips each Lambda folder and uploads it there
#   3. "aws cloudformation deploy" creates or updates the stack
#   4. prints the stack outputs
set -euo pipefail

TEMPLATE="${1:?usage: deploy-cfn.sh <template.yaml> <stack-name> [Key=Value ...]}"
STACK="${2:?usage: deploy-cfn.sh <template.yaml> <stack-name> [Key=Value ...]}"
shift 2

ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGION="$(aws configure get region || true)"
REGION="${AWS_REGION:-${REGION:-us-east-1}}"
ARTIFACTS="cfn-artifacts-${ACCOUNT}-${REGION}"
PACKAGED="$(mktemp -t packaged-XXXXXX).yaml"

echo "Account $ACCOUNT · Region $REGION · Stack $STACK"

if ! aws s3api head-bucket --bucket "$ARTIFACTS" 2>/dev/null; then
  echo "Creating the code-package bucket s3://$ARTIFACTS (one time)"
  if [ "$REGION" = "us-east-1" ]; then
    aws s3api create-bucket --bucket "$ARTIFACTS" >/dev/null
  else
    aws s3api create-bucket --bucket "$ARTIFACTS" --create-bucket-configuration LocationConstraint="$REGION" >/dev/null
  fi
  aws s3api put-public-access-block --bucket "$ARTIFACTS" \
    --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
fi

aws cloudformation package \
  --template-file "$TEMPLATE" \
  --s3-bucket "$ARTIFACTS" \
  --output-template-file "$PACKAGED" >/dev/null

PARAMS=()
if [ "$#" -gt 0 ]; then PARAMS=(--parameter-overrides "$@"); fi

aws cloudformation deploy \
  --template-file "$PACKAGED" \
  --stack-name "$STACK" \
  --capabilities CAPABILITY_IAM \
  --no-fail-on-empty-changeset \
  ${PARAMS[@]+"${PARAMS[@]}"}

aws cloudformation describe-stacks --stack-name "$STACK" \
  --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" --output table

echo "Delete it later with:  aws cloudformation delete-stack --stack-name $STACK"
