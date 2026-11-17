"""Lab 06 · Load balancer + Auto Scaling group of nginx servers across 2 AZs.

Costs about $0.05/hour while deployed: run `npx cdk destroy Lab06Ec2Website` after the lab.
"""

import re
from pathlib import Path

import aws_cdk as cdk
from aws_cdk import aws_autoscaling as autoscaling
from aws_cdk import aws_ec2 as ec2
from aws_cdk import aws_elasticloadbalancingv2 as elbv2
from aws_cdk import aws_iam as iam
from constructs import Construct

from .shared import from_repo


class Lab06Ec2WebsiteStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, repo_url: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        vpc = ec2.Vpc(
            self,
            "Vpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24)
            ],
        )

        # Same user data as the console lab, with your repository URL filled in
        script = Path(from_repo("labs/06-ec2-website/user-data.sh")).read_text()
        script = re.sub(r"^REPO_URL=.*$", f'REPO_URL="{repo_url}"', script, count=1, flags=re.MULTILINE)
        user_data = ec2.UserData.custom(script)

        role = iam.Role(
            self,
            "WebRole",
            assumed_by=iam.ServicePrincipal("ec2.amazonaws.com"),
            managed_policies=[iam.ManagedPolicy.from_aws_managed_policy_name("AmazonSSMManagedInstanceCore")],
        )

        # One security group for every server. The listener below opens it to the load balancer only.
        web_sg = ec2.SecurityGroup(self, "WebSg", vpc=vpc, description="Web servers: HTTP from the load balancer")

        # A launch template: the recipe for each server. (New accounts can't create the older
        # "launch configurations", so always use a launch template.)
        template = ec2.LaunchTemplate(
            self,
            "WebTemplate",
            instance_type=ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
            machine_image=ec2.MachineImage.latest_amazon_linux2023(),
            user_data=user_data,
            role=role,
            security_group=web_sg,
            associate_public_ip_address=True,
            require_imdsv2=True,
            block_devices=[
                ec2.BlockDevice(
                    device_name="/dev/xvda",
                    volume=ec2.BlockDeviceVolume.ebs(8, volume_type=ec2.EbsDeviceVolumeType.GP3, encrypted=True),
                )
            ],
        )

        asg = autoscaling.AutoScalingGroup(
            self,
            "WebServers",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            launch_template=template,
            min_capacity=2,
            max_capacity=4,
            health_checks=autoscaling.HealthChecks.with_additional_checks(
                additional_types=[autoscaling.AdditionalHealthCheckType.ELB],
                grace_period=cdk.Duration.minutes(3),
            ),
        )
        asg.scale_on_cpu_utilization("KeepCpuAt50", target_utilization_percent=50)

        alb = elbv2.ApplicationLoadBalancer(self, "LoadBalancer", vpc=vpc, internet_facing=True)
        listener = alb.add_listener("Http", port=80, open=True)
        listener.add_targets(
            "Web",
            port=80,
            targets=[asg],  # also opens the servers' security group to the load balancer only
            health_check=elbv2.HealthCheck(
                path="/health", interval=cdk.Duration.seconds(15), healthy_threshold_count=2
            ),
            deregistration_delay=cdk.Duration.seconds(30),
        )

        cdk.CfnOutput(self, "WebsiteUrl", value=f"http://{alb.load_balancer_dns_name}")
