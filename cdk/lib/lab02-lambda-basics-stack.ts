import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { LabFunction } from './shared';

/** Lab 02 · One function with a public function URL. */
export class Lab02LambdaBasicsStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const hello = new LabFunction(this, 'Hello', {
      codeDir: 'labs/02-lambda-basics/src',
      description: 'Lab 02 - hello from Lambda',
      environment: { GREETING: 'Hello' },
      timeout: cdk.Duration.seconds(5),
    });

    const url = hello.addFunctionUrl({ authType: lambda.FunctionUrlAuthType.NONE });

    new cdk.CfnOutput(this, 'FunctionUrl', { value: url.url, description: 'Open with ?name=Dana' });
    new cdk.CfnOutput(this, 'FunctionName', { value: hello.functionName });
  }
}
