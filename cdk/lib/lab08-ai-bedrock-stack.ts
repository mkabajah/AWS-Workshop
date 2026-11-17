import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import { LabFunction } from './shared';

export interface Lab08Props extends cdk.StackProps {
  /** Model or inference profile ID (cdk deploy -c modelId=eu.amazon.nova-micro-v1:0) */
  readonly modelId: string;
  readonly siteContext: string;
}

/** Lab 08 · An "ask me" endpoint: function URL → Lambda → Amazon Bedrock. */
export class Lab08AiBedrockStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Lab08Props) {
    super(scope, id, props);

    const ask = new LabFunction(this, 'Ask', {
      codeDir: 'labs/08-ai-bedrock/src',
      description: 'Lab 08 - answers questions with Amazon Bedrock',
      environment: { MODEL_ID: props.modelId, SITE_CONTEXT: props.siteContext },
      memorySize: 256,
      timeout: cdk.Duration.seconds(30),
    });
    // At most 2 answers at once: protects your credits if the URL gets shared
    (ask.node.defaultChild as lambda.CfnFunction).reservedConcurrentExecutions = 2;

    ask.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: [
        `arn:${this.partition}:bedrock:*::foundation-model/*`,
        `arn:${this.partition}:bedrock:*:${this.account}:inference-profile/*`,
      ],
    }));

    const url = ask.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: { allowedOrigins: ['*'], allowedMethods: [lambda.HttpMethod.POST], allowedHeaders: ['content-type'] },
    });

    new cdk.CfnOutput(this, 'AskUrl', { value: url.url });
  }
}
