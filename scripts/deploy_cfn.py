#!/usr/bin/env python3
"""Deploy any lab's CloudFormation template from the terminal.

    python scripts/deploy_cfn.py <template.yaml> <stack-name> [Key=Value ...]

Examples:
    python scripts/deploy_cfn.py labs/02-lambda-basics/cloudformation/lambda-basics.yaml lab02-hello
    python scripts/deploy_cfn.py labs/04-event-triggers/cloudformation/event-triggers.yaml lab04-triggers \\
        NotificationEmail=you@example.com

What it does:
    1. makes sure an S3 bucket exists for code packages (once per account and Region)
    2. "aws cloudformation package" zips each Lambda folder and uploads it there
    3. "aws cloudformation deploy" creates or updates the stack
    4. prints the stack outputs

Needs the AWS CLI (for step 2, which has no boto3 equivalent) and boto3.
"""

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError


def ensure_artifacts_bucket(s3, name, region):
    try:
        s3.head_bucket(Bucket=name)
        return
    except ClientError:
        pass

    print(f"Creating the code-package bucket s3://{name} (one time)")
    if region == "us-east-1":
        s3.create_bucket(Bucket=name)
    else:
        s3.create_bucket(Bucket=name, CreateBucketConfiguration={"LocationConstraint": region})
    s3.put_public_access_block(
        Bucket=name,
        PublicAccessBlockConfiguration={
            "BlockPublicAcls": True,
            "IgnorePublicAcls": True,
            "BlockPublicPolicy": True,
            "RestrictPublicBuckets": True,
        },
    )


def aws(*args):
    """Run an AWS CLI command and stop with its error message if it fails."""
    result = subprocess.run(["aws", *args], text=True)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(description="Package and deploy a lab's CloudFormation template")
    parser.add_argument("template", type=Path)
    parser.add_argument("stack")
    parser.add_argument("parameters", nargs="*", help="Key=Value pairs for the template's parameters")
    args = parser.parse_args()

    session = boto3.Session()
    region = session.region_name or "us-east-1"
    account = session.client("sts").get_caller_identity()["Account"]
    artifacts = f"cfn-artifacts-{account}-{region}"
    print(f"Account {account} · Region {region} · Stack {args.stack}")

    ensure_artifacts_bucket(session.client("s3", region_name=region), artifacts, region)

    with tempfile.TemporaryDirectory() as tmp:
        packaged = Path(tmp) / "packaged.yaml"
        aws(
            "cloudformation", "package",
            "--template-file", str(args.template),
            "--s3-bucket", artifacts,
            "--output-template-file", str(packaged),
            "--region", region,
        )  # fmt: skip

        deploy = [
            "cloudformation", "deploy",
            "--template-file", str(packaged),
            "--stack-name", args.stack,
            "--capabilities", "CAPABILITY_IAM",
            "--no-fail-on-empty-changeset",
            "--region", region,
        ]  # fmt: skip
        if args.parameters:
            deploy += ["--parameter-overrides", *args.parameters]
        aws(*deploy)

    stack = session.client("cloudformation", region_name=region).describe_stacks(StackName=args.stack)["Stacks"][0]
    print("\nOutputs:")
    for output in stack.get("Outputs", []):
        print(f"  {output['OutputKey']:<24} {output['OutputValue']}")

    print(f"\nDelete it later with:  aws cloudformation delete-stack --stack-name {args.stack}")


if __name__ == "__main__":
    main()
