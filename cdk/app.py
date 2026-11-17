#!/usr/bin/env python3
"""One CDK app, one stack per lab. Deploy ONE lab at a time, never --all:

npx cdk deploy Lab02LambdaBasics
npx cdk deploy Lab04EventTriggers -c email=you@example.com
npx cdk deploy Lab06Ec2Website -c repoUrl=https://github.com/you/AWS-Workshop.git
npx cdk deploy Lab07Capstone -c stage=2
npx cdk destroy Lab05LambdaRds
"""

import os

import aws_cdk as cdk

from stacks.lab01_static_site import Lab01StaticSiteStack
from stacks.lab02_lambda_basics import Lab02LambdaBasicsStack
from stacks.lab03_api_dynamodb import Lab03ApiDynamoDbStack
from stacks.lab04_event_triggers import Lab04EventTriggersStack
from stacks.lab05_lambda_rds import Lab05LambdaRdsStack
from stacks.lab06_ec2_website import Lab06Ec2WebsiteStack
from stacks.lab07_capstone import Lab07CapstoneStack
from stacks.lab08_ai_bedrock import Lab08AiBedrockStack

app = cdk.App()


def ctx(key, fallback):
    value = app.node.try_get_context(key)
    return fallback if value is None else str(value)


env = cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION"))

Lab01StaticSiteStack(app, "Lab01StaticSite", env=env, description="Lab 01 - static website on S3 + CloudFront")
Lab02LambdaBasicsStack(app, "Lab02LambdaBasics", env=env, description="Lab 02 - Lambda basics")
Lab03ApiDynamoDbStack(app, "Lab03ApiDynamoDb", env=env, description="Lab 03 - API Gateway + Lambda + DynamoDB")
Lab04EventTriggersStack(
    app,
    "Lab04EventTriggers",
    env=env,
    description="Lab 04 - S3, SQS and schedule triggers",
    notification_email=app.node.try_get_context("email"),
)
Lab05LambdaRdsStack(app, "Lab05LambdaRds", env=env, description="Lab 05 - Lambda + RDS PostgreSQL")
Lab06Ec2WebsiteStack(
    app,
    "Lab06Ec2Website",
    env=env,
    description="Lab 06 - EC2 web servers behind a load balancer",
    repo_url=ctx("repoUrl", "https://github.com/mkabajah/AWS-Workshop.git"),
)

stage = int(ctx("stage", "1"))
if stage not in (1, 2, 3):
    raise ValueError(f"stage must be 1, 2 or 3 (got {stage})")
Lab07CapstoneStack(app, "Lab07Capstone", env=env, stage=stage, description=f"Lab 07 - capstone website, stage {stage}")

Lab08AiBedrockStack(
    app,
    "Lab08AiBedrock",
    env=env,
    description="Lab 08 - AI answers with Amazon Bedrock",
    model_id=ctx("modelId", "us.amazon.nova-micro-v1:0"),
    site_context=ctx("siteContext", "Your Name is a computer science student learning AWS."),
    reserved_concurrency=int(ctx("reservedConcurrency", "0")),
)

cdk.Tags.of(app).add("project", "aws-workshop")
app.synth()
