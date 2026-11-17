"""Lab 02 · One function with a public function URL."""

import aws_cdk as cdk
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .shared import LabFunction


class Lab02LambdaBasicsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        hello = LabFunction(
            self,
            "Hello",
            code_dir="labs/02-lambda-basics/src",
            description="Lab 02 - hello from Lambda",
            environment={"GREETING": "Hello"},
            timeout=cdk.Duration.seconds(5),
        )

        url = hello.add_function_url(auth_type=lambda_.FunctionUrlAuthType.NONE)

        cdk.CfnOutput(self, "FunctionUrl", value=url.url, description="Open with ?name=Dana")
        cdk.CfnOutput(self, "FunctionName", value=hello.function_name)
