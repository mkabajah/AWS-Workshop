import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as apigw from 'aws-cdk-lib/aws-apigatewayv2';
import { HttpLambdaIntegration } from 'aws-cdk-lib/aws-apigatewayv2-integrations';
import { LabFunction } from './shared';

/** Lab 03 · Notes API: HTTP API → Lambda → DynamoDB. */
export class Lab03ApiDynamoDbStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const table = new dynamodb.TableV2(this, 'Notes', {
      partitionKey: { name: 'id', type: dynamodb.AttributeType.STRING },
      billing: dynamodb.Billing.onDemand(),
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const notesFn = new LabFunction(this, 'NotesFunction', {
      codeDir: 'labs/03-api-dynamodb/src',
      description: 'Lab 03 - notes API',
      environment: { TABLE_NAME: table.tableName },
      memorySize: 256,
    });
    table.grantReadWriteData(notesFn); // least privilege: this table only

    const api = new apigw.HttpApi(this, 'NotesApi', {
      corsPreflight: {
        allowOrigins: ['*'],
        allowMethods: [apigw.CorsHttpMethod.GET, apigw.CorsHttpMethod.POST, apigw.CorsHttpMethod.DELETE],
        allowHeaders: ['content-type'],
      },
    });
    const integration = new HttpLambdaIntegration('NotesIntegration', notesFn);
    api.addRoutes({ path: '/notes', methods: [apigw.HttpMethod.GET, apigw.HttpMethod.POST], integration });
    api.addRoutes({ path: '/notes/{id}', methods: [apigw.HttpMethod.GET, apigw.HttpMethod.DELETE], integration });

    new cdk.CfnOutput(this, 'ApiUrl', { value: api.apiEndpoint, description: 'curl <ApiUrl>/notes' });
    new cdk.CfnOutput(this, 'TableName', { value: table.tableName });
  }
}
