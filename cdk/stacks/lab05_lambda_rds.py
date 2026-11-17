"""Lab 05 · Lambda + RDS PostgreSQL in private subnets.

Costs about $0.04/hour while deployed: run `npx cdk destroy Lab05LambdaRds` after the lab.
"""

from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_rds as rds
from constructs import Construct

from .shared import LabFunction, from_repo


class Lab05LambdaRdsStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Private network in 2 AZs, no NAT gateway (and so no NAT cost)
        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="private", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=24)
            ],
        )
        private = ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_ISOLATED)

        db = rds.DatabaseInstance(
            self,
            "Database",
            engine=rds.DatabaseInstanceEngine.postgres(version=rds.PostgresEngineVersion.VER_17_6),
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MICRO),
            vpc=vpc,
            vpc_subnets=private,
            database_name="shop",
            credentials=rds.Credentials.from_generated_secret("postgres"),  # password lives in Secrets Manager
            allocated_storage=20,
            storage_type=rds.StorageType.GP3,
            storage_encrypted=True,
            multi_az=False,
            publicly_accessible=False,
            backup_retention=cdk.Duration.days(1),
            deletion_protection=False,
            removal_policy=cdk.RemovalPolicy.DESTROY,  # lab only: real data deserves SNAPSHOT
        )

        # The function has no internet: it reaches Secrets Manager through a private endpoint
        vpc.add_interface_endpoint("SecretsManager", service=ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER)

        # The deployed folder must include pg8000 and the RDS certificates: scripts/package.py builds it.
        code_dir = "labs/05-lambda-rds/build"
        if not Path(from_repo(code_dir, "global-bundle.pem")).exists():
            code_dir = "labs/05-lambda-rds/src"
            cdk.Annotations.of(self).add_warning_v2(
                "lab05:no-build",
                'Run "python labs/05-lambda-rds/scripts/package.py" before deploying Lab05LambdaRds, '
                "or the function cannot load pg8000",
            )

        products = LabFunction(
            self,
            "Products",
            code_dir=code_dir,
            description="Lab 05 - reads and writes PostgreSQL",
            memory_size=256,
            timeout=cdk.Duration.seconds(15),
            vpc=vpc,
            vpc_subnets=private,
            environment={
                "DB_HOST": db.db_instance_endpoint_address,
                "DB_NAME": "shop",
                "SECRET_ARN": db.secret.secret_arn,
            },
        )

        db.connections.allow_default_port_from(products, "Lambda to PostgreSQL")  # security group rule
        db.secret.grant_read(products)  # IAM permission for this one secret

        cdk.CfnOutput(self, "FunctionName", value=products.function_name)
        cdk.CfnOutput(self, "DatabaseEndpoint", value=db.db_instance_endpoint_address)
