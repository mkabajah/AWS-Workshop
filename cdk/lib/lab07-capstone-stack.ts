import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { fromRepo } from './shared';

export interface Lab07CapstoneProps extends cdk.StackProps {
  /** 1 = static site, 2 = + API and database, 3 = + S3 upload trigger */
  readonly stage: number;
}

/**
 * Lab 07 · Capstone: the personal website, grown in three stages.
 *   npx cdk deploy Lab07Capstone -c stage=1 | 2 | 3
 */
export class Lab07CapstoneStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Lab07CapstoneProps) {
    super(scope, id, props);
    const { stage } = props;

    // ── Stage 1: the website ────────────────────────────────────────────────
    // Same as the console lab: a private bucket, and CloudFront as the only reader.
    const siteBucket = new s3.Bucket(this, 'SiteBucket', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY, // demo only: cdk destroy removes everything
      autoDeleteObjects: true,
    });

    const distribution = new cloudfront.Distribution(this, 'Cdn', {
      comment: 'Personal website (AWS Foundations demo)',
      defaultRootObject: 'index.html',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(siteBucket),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        // HSTS, no-sniff, frame and referrer protection on every page
        responseHeadersPolicy: cloudfront.ResponseHeadersPolicy.SECURITY_HEADERS,
      },
      // A missing page shows our 404.html (S3 answers 403 for missing objects behind OAC)
      errorResponses: [403, 404].map((httpStatus) => ({
        httpStatus,
        responseHttpStatus: 404,
        responsePagePath: '/404.html',
        ttl: cdk.Duration.minutes(5),
      })),
    });

    const config: Record<string, unknown> = { stage, deployedWith: 'AWS CDK' };

    // ── Stage 2: an API and a database ──────────────────────────────────────
    let table: dynamodb.TableV2 | undefined;
    if (stage >= 2) {
      table = new dynamodb.TableV2(this, 'SiteData', {
        partitionKey: { name: 'pk', type: dynamodb.AttributeType.STRING },
        sortKey: { name: 'sk', type: dynamodb.AttributeType.STRING },
        billing: dynamodb.Billing.onDemand(), // pay per request, nothing when idle
        removalPolicy: cdk.RemovalPolicy.DESTROY,
      });

      const apiFunction = new lambda.Function(this, 'ApiFunction', {
        runtime: lambda.Runtime.NODEJS_22_X,
        architecture: lambda.Architecture.ARM_64, // Graviton: about 20% cheaper
        handler: 'index.handler',
        code: lambda.Code.fromAsset(fromRepo('labs/07-capstone/lambda/api')),
        memorySize: 128,
        timeout: cdk.Duration.seconds(5),
        environment: { TABLE_NAME: table.tableName },
        logGroup: new logs.LogGroup(this, 'ApiLogs', {
          retention: logs.RetentionDays.ONE_WEEK,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      });
      table.grantReadWriteData(apiFunction); // least privilege: this table only

      const api = new apigw.HttpApi(this, 'Api', { description: 'Personal website API' });

      // Protect the bill: at most 10 requests a second (bursts of 20) reach Lambda.
      const stageResource = api.defaultStage!.node.defaultChild as apigw.CfnStage;
      stageResource.defaultRouteSettings = { throttlingRateLimit: 10, throttlingBurstLimit: 20 };

      api.addRoutes({
        path: '/api/{proxy+}',
        methods: [apigw.HttpMethod.GET, apigw.HttpMethod.POST],
        integration: new HttpLambdaIntegration('ApiIntegration', apiFunction),
      });

      // CloudFront sends /api/* to the API, so the site and the API share one HTTPS domain (no CORS).
      const apiDomain = cdk.Fn.select(2, cdk.Fn.split('/', api.apiEndpoint));
      distribution.addBehavior('/api/*', new origins.HttpOrigin(apiDomain), {
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
        cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
        originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
      });

      new cdk.CfnOutput(this, 'ApiLogGroup', { value: apiFunction.logGroup.logGroupName });
      new cdk.CfnOutput(this, 'TableName', { value: table.tableName });
    }

    // ── Stage 3: an event trigger ───────────────────────────────────────────
    if (stage >= 3 && table) {
      const uploadsBucket = new s3.Bucket(this, 'UploadsBucket', {
        blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
        encryption: s3.BucketEncryption.S3_MANAGED,
        enforceSSL: true,
        removalPolicy: cdk.RemovalPolicy.DESTROY,
        autoDeleteObjects: true,
      });

      const onUpload = new lambda.Function(this, 'OnUploadFunction', {
        runtime: lambda.Runtime.NODEJS_22_X,
        architecture: lambda.Architecture.ARM_64,
        handler: 'index.handler',
        code: lambda.Code.fromAsset(fromRepo('labs/07-capstone/lambda/on-upload')),
        memorySize: 128,
        timeout: cdk.Duration.seconds(10),
        environment: { TABLE_NAME: table.tableName },
        logGroup: new logs.LogGroup(this, 'OnUploadLogs', {
          retention: logs.RetentionDays.ONE_WEEK,
          removalPolicy: cdk.RemovalPolicy.DESTROY,
        }),
      });
      table.grantWriteData(onUpload);

      // The trigger: every new object in the bucket runs the function.
      uploadsBucket.addEventNotification(s3.EventType.OBJECT_CREATED, new s3n.LambdaDestination(onUpload));

      new cdk.CfnOutput(this, 'UploadsBucketName', { value: uploadsBucket.bucketName });
      new cdk.CfnOutput(this, 'OnUploadLogGroup', { value: onUpload.logGroup.logGroupName });
    }

    // Upload the site, plus a config.json that tells the page which features exist.
    new s3deploy.BucketDeployment(this, 'DeploySite', {
      sources: [
        s3deploy.Source.asset(fromRepo('site')),
        s3deploy.Source.jsonData('config.json', config),
      ],
      destinationBucket: siteBucket,
      distribution, // invalidates the CloudFront cache after each deploy
      distributionPaths: ['/*'],
    });

    new cdk.CfnOutput(this, 'WebsiteUrl', { value: `https://${distribution.distributionDomainName}` });
    new cdk.CfnOutput(this, 'SiteBucketName', { value: siteBucket.bucketName });
    new cdk.CfnOutput(this, 'DistributionId', { value: distribution.distributionId });
  }
}
