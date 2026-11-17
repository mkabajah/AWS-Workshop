import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as fs from 'fs';
import { LabFunction, fromRepo } from './shared';

/**
 * Lab 05 · Lambda + RDS PostgreSQL in private subnets.
 * Costs about $0.04/hour while deployed: run `npx cdk destroy Lab05LambdaRds` after the lab.
 */
export class Lab05LambdaRdsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Private network in 2 AZs, no NAT gateway (and so no NAT cost)
    const vpc = new ec2.Vpc(this, 'Vpc', {
      maxAzs: 2,
      natGateways: 0,
      subnetConfiguration: [{ name: 'private', subnetType: ec2.SubnetType.PRIVATE_ISOLATED, cidrMask: 24 }],
    });

    const db = new rds.DatabaseInstance(this, 'Database', {
      engine: rds.DatabaseInstanceEngine.postgres({ version: rds.PostgresEngineVersion.VER_17_6 }),
      instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MICRO),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      databaseName: 'shop',
      credentials: rds.Credentials.fromGeneratedSecret('postgres'), // password lives in Secrets Manager
      allocatedStorage: 20,
      storageType: rds.StorageType.GP3,
      storageEncrypted: true,
      multiAz: false,
      publiclyAccessible: false,
      backupRetention: cdk.Duration.days(1),
      deletionProtection: false,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // lab only: real data deserves SNAPSHOT
    });

    // The function has no internet: it reaches Secrets Manager through a private endpoint
    vpc.addInterfaceEndpoint('SecretsManager', { service: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER });

    // The function's folder must include the pg driver: run `npm ci --omit=dev` in labs/05-lambda-rds/src first
    if (!fs.existsSync(fromRepo('labs/05-lambda-rds/src/node_modules/pg'))) {
      cdk.Annotations.of(this).addWarningV2('lab05:no-pg', 'Run "npm ci --omit=dev" in labs/05-lambda-rds/src before deploying Lab05LambdaRds, or the function cannot load pg');
    }
    const products = new LabFunction(this, 'Products', {
      codeDir: 'labs/05-lambda-rds/src',
      description: 'Lab 05 - reads and writes PostgreSQL',
      memorySize: 256,
      timeout: cdk.Duration.seconds(15),
      vpc,
      vpcSubnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      environment: {
        DB_HOST: db.dbInstanceEndpointAddress,
        DB_NAME: 'shop',
        SECRET_ARN: db.secret!.secretArn,
        NODE_EXTRA_CA_CERTS: '/var/runtime/ca-cert.pem',
      },
    });

    db.connections.allowDefaultPortFrom(products, 'Lambda to PostgreSQL'); // security group rule
    db.secret!.grantRead(products); // IAM permission for this one secret

    new cdk.CfnOutput(this, 'FunctionName', { value: products.functionName });
    new cdk.CfnOutput(this, 'DatabaseEndpoint', { value: db.dbInstanceEndpointAddress });
  }
}
