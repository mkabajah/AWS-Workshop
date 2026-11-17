"""What every lab stack shares: paths into the repository and a standard Lambda function."""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_logs as logs
from constructs import Construct

# Root of the repository, so stacks can point at labs/ and site/.
REPO_ROOT = Path(__file__).resolve().parents[2]


def from_repo(*parts):
    return str(REPO_ROOT.joinpath(*parts))


class LabFunction(lambda_.Function):
    """The defaults every lab function shares: Python 3.13 on Graviton (arm64),
    a small memory size, and logs that are deleted after a week.

    code_dir is the folder that holds lambda_function.py, relative to the repository root.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        *,
        code_dir: str,
        description: str,
        environment: dict | None = None,
        memory_size: int = 128,
        timeout: cdk.Duration | None = None,
        vpc: ec2.IVpc | None = None,
        vpc_subnets: ec2.SubnetSelection | None = None,
    ) -> None:
        super().__init__(
            scope,
            construct_id,
            runtime=lambda_.Runtime.PYTHON_3_13,
            architecture=lambda_.Architecture.ARM_64,
            handler="lambda_function.lambda_handler",
            code=lambda_.Code.from_asset(from_repo(code_dir), exclude=["__pycache__", "*.pyc"]),
            description=description,
            environment=environment,
            memory_size=memory_size,
            timeout=timeout or cdk.Duration.seconds(10),
            vpc=vpc,
            vpc_subnets=vpc_subnets,
            log_group=logs.LogGroup(
                scope,
                f"{construct_id}Logs",
                retention=logs.RetentionDays.ONE_WEEK,
                removal_policy=cdk.RemovalPolicy.DESTROY,
            ),
        )
