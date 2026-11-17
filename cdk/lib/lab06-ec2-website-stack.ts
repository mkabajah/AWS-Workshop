import * as fs from 'fs';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as autoscaling from 'aws-cdk-lib/aws-autoscaling';
import * as elbv2 from 'aws-cdk-lib/aws-elasticloadbalancingv2';
import { fromRepo } from './shared';

export interface Lab06Props extends cdk.StackProps {
  /** Your fork of this repository (cdk deploy -c repoUrl=https://github.com/you/aws-foundations-labs.git) */
  readonly repoUrl: string;
}

/**
 * Lab 06 · Load balancer + Auto Scaling group of nginx servers across 2 AZs.
 * Costs about $0.05/hour while deployed: run `npx cdk destroy Lab06Ec2Website` after the lab.
 */
export class Lab06Ec2WebsiteStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Lab06Props) {
    super(scope, id, props);

    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [{ name: 'public', subnetType: ec2.SubnetType.PUBLIC, cidrMask: 24 }],
    });

    // Same user data as the console lab, with your repository URL filled in
    const script = fs.readFileSync(fromRepo('labs/06-ec2-website/user-data.sh'), 'utf8')
      .replace(/^REPO_URL=.*$/m, `REPO_URL="${props.repoUrl}"`);
    const userData = ec2.UserData.custom(script);

    const role = new iam.Role(this, 'WebRole', {
      assumedBy: new iam.ServicePrincipal('ec2.amazonaws.com'),
      managedPolicies: [iam.ManagedPolicy.fromAwsManagedPolicyName('AmazonSSMManagedInstanceCore')],
    });

    const asg = new autoscaling.AutoScalingGroup(this, 'WebServers', {
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PUBLIC },
      associatePublicIpAddress: true,
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T3, ec2.InstanceSize.MICRO),
      machineImage: ec2.MachineImage.latestAmazonLinux2023(),
      userData,
      role,
      requireImdsv2: true,
      minCapacity: 2,
      maxCapacity: 4,
      healthChecks: autoscaling.HealthChecks.withAdditionalChecks({
        additionalTypes: [autoscaling.AdditionalHealthCheckType.ELB],
        gracePeriod: cdk.Duration.minutes(3),
      }),
      blockDevices: [{
        deviceName: '/dev/xvda',
        volume: autoscaling.BlockDeviceVolume.ebs(8, { volumeType: autoscaling.EbsDeviceVolumeType.GP3, encrypted: true }),
      }],
    });
    asg.scaleOnCpuUtilization('KeepCpuAt50', { targetUtilizationPercent: 50 });

    const alb = new elbv2.ApplicationLoadBalancer(this, 'LoadBalancer', { vpc, internetFacing: true });
    const listener = alb.addListener('Http', { port: 80, open: true });
    listener.addTargets('Web', {
      port: 80,
      targets: [asg], // also opens the servers' security group to the load balancer only
      healthCheck: { path: '/health', interval: cdk.Duration.seconds(15), healthyThresholdCount: 2 },
      deregistrationDelay: cdk.Duration.seconds(30),
    });

    new cdk.CfnOutput(this, 'WebsiteUrl', { value: `http://${alb.loadBalancerDnsName}` });
  }
}
