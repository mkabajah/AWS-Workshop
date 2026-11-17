"""Lab 01 · Private S3 bucket + CloudFront (OAC), with the site uploaded for you."""

import aws_cdk as cdk
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from constructs import Construct

from .shared import from_repo


class Lab01StaticSiteStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        distribution = cloudfront.Distribution(
            self,
            "Cdn",
            comment="Lab 01 static website (CDK)",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
            ),
            error_responses=[
                cloudfront.ErrorResponse(http_status=status, response_http_status=404, response_page_path="/404.html")
                for status in (403, 404)
            ],
        )

        s3deploy.BucketDeployment(
            self,
            "UploadSite",
            sources=[s3deploy.Source.asset(from_repo("site"))],
            destination_bucket=bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        cdk.CfnOutput(self, "WebsiteUrl", value=f"https://{distribution.distribution_domain_name}")
