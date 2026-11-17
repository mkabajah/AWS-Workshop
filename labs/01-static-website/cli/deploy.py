#!/usr/bin/env python3
"""Lab 01 · Upload the website and clear the CloudFront cache, with boto3.

    python labs/01-static-website/cli/deploy.py <bucket-name> <distribution-id>

Works with a bucket made in the console or by the CloudFormation template.
With the template, read both values from its Outputs:
    aws cloudformation describe-stacks --stack-name lab01-static-site \\
        --query "Stacks[0].Outputs" --output table

Uploads only files that changed (compares MD5 with the ETag), deletes files you
removed, sets the right Content-Type, then invalidates the CloudFront cache.
"""

import argparse
import hashlib
import mimetypes
import time
from pathlib import Path

import boto3

SITE_DIR = Path(__file__).resolve().parents[3] / "site"
SKIP = {".DS_Store", "Thumbs.db"}

# HTML must always be fresh; CSS, JS and images can be cached for a day.
CACHE_HTML = "no-cache"
CACHE_ASSETS = "public, max-age=86400"


def local_files():
    for path in sorted(SITE_DIR.rglob("*")):
        if path.is_file() and path.name not in SKIP:
            yield path.relative_to(SITE_DIR).as_posix(), path


def remote_etags(s3, bucket):
    etags = {}
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            etags[obj["Key"]] = obj["ETag"].strip('"')
    return etags


def main():
    parser = argparse.ArgumentParser(description="Deploy the site/ folder to S3 + CloudFront")
    parser.add_argument("bucket")
    parser.add_argument("distribution_id")
    args = parser.parse_args()

    session = boto3.Session()
    s3 = session.client("s3")
    cloudfront = session.client("cloudfront")

    print("Deploying as:", session.client("sts").get_caller_identity()["Arn"])

    print(f"1/3 Uploading {SITE_DIR} -> s3://{args.bucket} (only changed files)")
    remote = remote_etags(s3, args.bucket)
    uploaded = 0
    for key, path in local_files():
        body = path.read_bytes()
        if remote.pop(key, None) == hashlib.md5(body).hexdigest():  # noqa: S324 - matches the S3 ETag, not security
            continue
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        s3.put_object(
            Bucket=args.bucket,
            Key=key,
            Body=body,
            ContentType=content_type,
            CacheControl=CACHE_HTML if key.endswith(".html") else CACHE_ASSETS,
        )
        print("   uploaded", key)
        uploaded += 1

    print(f"2/3 Removing {len(remote)} file(s) that are no longer in site/")
    for key in remote:
        s3.delete_object(Bucket=args.bucket, Key=key)
        print("   deleted", key)

    print("3/3 Clearing the CloudFront cache")
    invalidation = cloudfront.create_invalidation(
        DistributionId=args.distribution_id,
        InvalidationBatch={"Paths": {"Quantity": 1, "Items": ["/*"]}, "CallerReference": str(time.time())},
    )
    print("   invalidation", invalidation["Invalidation"]["Id"], invalidation["Invalidation"]["Status"])

    print(f"Done: {uploaded} uploaded. Refresh the site in about a minute.")


if __name__ == "__main__":
    main()
