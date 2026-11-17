import * as path from 'path';
import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';

/** Root of the repository, so stacks can point at labs/ and site/. */
export const REPO_ROOT = path.join(__dirname, '../..');
export const fromRepo = (...parts: string[]) => path.join(REPO_ROOT, ...parts);

export interface LabFunctionProps {
  /** Folder that holds index.mjs, relative to the repository root */
  readonly codeDir: string;
  readonly description: string;
  readonly environment?: Record<string, string>;
  readonly memorySize?: number;
  readonly timeout?: cdk.Duration;
  /** Run the function inside a VPC (Lab 05) */
  readonly vpc?: ec2.IVpc;
  readonly vpcSubnets?: ec2.SubnetSelection;
}

/**
 * The defaults every lab function shares: Node.js 22 on Graviton (arm64),
 * a small memory size, and logs that are deleted after a week.
 */
export class LabFunction extends lambda.Function {
  constructor(scope: Construct, id: string, props: LabFunctionProps) {
    super(scope, id, {
      runtime: lambda.Runtime.NODEJS_22_X,
      architecture: lambda.Architecture.ARM_64,
      handler: 'index.handler',
      code: lambda.Code.fromAsset(fromRepo(props.codeDir)),
      description: props.description,
      environment: props.environment,
      memorySize: props.memorySize ?? 128,
      timeout: props.timeout ?? cdk.Duration.seconds(10),
      vpc: props.vpc,
      vpcSubnets: props.vpcSubnets,
      logGroup: new logs.LogGroup(scope, `${id}Logs`, {
        retention: logs.RetentionDays.ONE_WEEK,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      }),
    });
  }
}
