"""Lab 08 · An "ask me" endpoint: function URL -> Lambda -> Amazon Bedrock."""

import aws_cdk as cdk
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from constructs import Construct

from .shared import LabFunction


class Lab08AiBedrockStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        model_id: str,
        site_context: str,
        reserved_concurrency: int = 0,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        ask = LabFunction(
            self,
            "Ask",
            code_dir="labs/08-ai-bedrock/src",
            description="Lab 08 - answers questions with Amazon Bedrock",
            environment={"MODEL_ID": model_id, "SITE_CONTEXT": site_context},
            memory_size=256,
            timeout=cdk.Duration.seconds(30),
        )
        # -c reservedConcurrency=2 caps it at 2 answers at once. Off by default: new accounts have a
        # concurrency quota of 10 and AWS keeps 10 unreserved, so any reservation fails there.
        if reserved_concurrency > 0:
            ask.node.default_child.reserved_concurrent_executions = reserved_concurrency

        ask.add_to_role_policy(
            iam.PolicyStatement(
                actions=["bedrock:InvokeModel"],
                resources=[
                    f"arn:{self.partition}:bedrock:*::foundation-model/*",
                    f"arn:{self.partition}:bedrock:*:{self.account}:inference-profile/*",
                ],
            )
        )

        url = ask.add_function_url(
            auth_type=lambda_.FunctionUrlAuthType.NONE,
            cors=lambda_.FunctionUrlCorsOptions(
                allowed_origins=["*"], allowed_methods=[lambda_.HttpMethod.POST], allowed_headers=["content-type"]
            ),
        )

        cdk.CfnOutput(self, "AskUrl", value=url.url)
