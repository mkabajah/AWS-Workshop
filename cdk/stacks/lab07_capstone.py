"""Lab 07 · Capstone: the personal website, grown in three stages.

  npx cdk deploy Lab07Capstone -c stage=1 | 2 | 3

1 = static site, 2 = + API and database, 3 = + S3 upload trigger
"""

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_cloudfront as cloudfront
from aws_cdk import aws_cloudfront_origins as origins
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct

from .shared import LabFunction, from_repo


class Lab07CapstoneStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, stage: int, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ── Stage 1: the website ────────────────────────────────────────────
        # Same as the console lab: a private bucket, and CloudFront as the only reader.
        site_bucket = s3.Bucket(
            self,
            "SiteBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,  # demo only: cdk destroy removes everything
            auto_delete_objects=True,
        )

        distribution = cloudfront.Distribution(
            self,
            "Cdn",
            comment="Personal website (AWS Foundations demo)",
            default_root_object="index.html",
            default_behavior=cloudfront.BehaviorOptions(
                origin=origins.S3BucketOrigin.with_origin_access_control(site_bucket),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                # HSTS, no-sniff, frame and referrer protection on every page
                response_headers_policy=cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
            ),
            # A missing page shows our 404.html (S3 answers 403 for missing objects behind OAC)
            error_responses=[
                cloudfront.ErrorResponse(
                    http_status=status,
                    response_http_status=404,
                    response_page_path="/404.html",
                    ttl=cdk.Duration.minutes(5),
                )
                for status in (403, 404)
            ],
        )

        config = {"stage": stage, "deployedWith": "AWS CDK"}

        # ── Stage 2: an API and a database ──────────────────────────────────
        table = None
        if stage >= 2:
            table = dynamodb.TableV2(
                self,
                "SiteData",
                partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),
                billing=dynamodb.Billing.on_demand(),  # pay per request, nothing when idle
                removal_policy=cdk.RemovalPolicy.DESTROY,
            )

            api_function = LabFunction(
                self,
                "ApiFunction",
                code_dir="labs/07-capstone/lambda/api",
                description="Lab 07 - the website API",
                environment={"TABLE_NAME": table.table_name},
                timeout=cdk.Duration.seconds(5),
            )
            table.grant_read_write_data(api_function)  # least privilege: this table only

            api = apigw.HttpApi(self, "Api", description="Personal website API")

            # Protect the bill: at most 10 requests a second (bursts of 20) reach Lambda.
            stage_resource = api.default_stage.node.default_child
            stage_resource.default_route_settings = apigw.CfnStage.RouteSettingsProperty(
                throttling_rate_limit=10, throttling_burst_limit=20
            )

            api.add_routes(
                path="/api/{proxy+}",
                methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST],
                integration=HttpLambdaIntegration("ApiIntegration", api_function),
            )

            # CloudFront sends /api/* to the API, so the site and the API share one HTTPS domain (no CORS).
            api_domain = cdk.Fn.select(2, cdk.Fn.split("/", api.api_endpoint))
            distribution.add_behavior(
                "/api/*",
                origins.HttpOrigin(api_domain),
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_ALL,
                cache_policy=cloudfront.CachePolicy.CACHING_DISABLED,
                origin_request_policy=cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
            )

            cdk.CfnOutput(self, "ApiLogGroup", value=api_function.log_group.log_group_name)
            cdk.CfnOutput(self, "TableName", value=table.table_name)

        # ── Stage 3: an event trigger ───────────────────────────────────────
        if stage >= 3 and table is not None:
            uploads_bucket = s3.Bucket(
                self,
                "UploadsBucket",
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                enforce_ssl=True,
                removal_policy=cdk.RemovalPolicy.DESTROY,
                auto_delete_objects=True,
            )

            on_upload = LabFunction(
                self,
                "OnUploadFunction",
                code_dir="labs/07-capstone/lambda/on-upload",
                description="Lab 07 - records every upload",
                environment={"TABLE_NAME": table.table_name},
            )
            table.grant_write_data(on_upload)

            # The trigger: every new object in the bucket runs the function.
            uploads_bucket.add_event_notification(s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(on_upload))

            cdk.CfnOutput(self, "UploadsBucketName", value=uploads_bucket.bucket_name)
            cdk.CfnOutput(self, "OnUploadLogGroup", value=on_upload.log_group.log_group_name)

        # Upload the site, plus a config.json that tells the page which features exist.
        s3deploy.BucketDeployment(
            self,
            "DeploySite",
            sources=[
                s3deploy.Source.asset(from_repo("site")),
                s3deploy.Source.json_data("config.json", config),
            ],
            destination_bucket=site_bucket,
            distribution=distribution,  # invalidates the CloudFront cache after each deploy
            distribution_paths=["/*"],
        )

        cdk.CfnOutput(self, "WebsiteUrl", value=f"https://{distribution.distribution_domain_name}")
        cdk.CfnOutput(self, "SiteBucketName", value=site_bucket.bucket_name)
        cdk.CfnOutput(self, "DistributionId", value=distribution.distribution_id)
