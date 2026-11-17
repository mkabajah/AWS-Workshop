"""Lab 03 · Notes API: HTTP API -> Lambda -> DynamoDB."""

import aws_cdk as cdk
from aws_cdk import aws_apigatewayv2 as apigw
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from constructs import Construct

from .shared import LabFunction


class Lab03ApiDynamoDbStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        table = dynamodb.TableV2(
            self,
            "Notes",
            partition_key=dynamodb.Attribute(name="id", type=dynamodb.AttributeType.STRING),
            billing=dynamodb.Billing.on_demand(),
            removal_policy=cdk.RemovalPolicy.DESTROY,
        )

        notes_fn = LabFunction(
            self,
            "NotesFunction",
            code_dir="labs/03-api-dynamodb/src",
            description="Lab 03 - notes API",
            environment={"TABLE_NAME": table.table_name},
            memory_size=256,
        )
        table.grant_read_write_data(notes_fn)  # least privilege: this table only

        api = apigw.HttpApi(
            self,
            "NotesApi",
            cors_preflight=apigw.CorsPreflightOptions(
                allow_origins=["*"],
                allow_methods=[apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.DELETE],
                allow_headers=["content-type"],
            ),
        )
        integration = HttpLambdaIntegration("NotesIntegration", notes_fn)
        api.add_routes(path="/notes", methods=[apigw.HttpMethod.GET, apigw.HttpMethod.POST], integration=integration)
        api.add_routes(
            path="/notes/{id}", methods=[apigw.HttpMethod.GET, apigw.HttpMethod.DELETE], integration=integration
        )

        cdk.CfnOutput(self, "ApiUrl", value=api.api_endpoint, description="curl <ApiUrl>/notes")
        cdk.CfnOutput(self, "TableName", value=table.table_name)
