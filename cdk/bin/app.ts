#!/usr/bin/env node
// One CDK app, one stack per lab. Deploy ONE lab at a time, never --all:
//
//   npx cdk deploy Lab02LambdaBasics
//   npx cdk deploy Lab04EventTriggers -c email=you@example.com
//   npx cdk deploy Lab06Ec2Website -c repoUrl=https://github.com/you/aws-foundations-labs.git
//   npx cdk deploy Lab07Capstone -c stage=2
//   npx cdk destroy Lab05LambdaRds
//
import * as cdk from 'aws-cdk-lib';
import { Lab01StaticSiteStack } from '../lib/lab01-static-site-stack';
import { Lab02LambdaBasicsStack } from '../lib/lab02-lambda-basics-stack';
import { Lab03ApiDynamoDbStack } from '../lib/lab03-api-dynamodb-stack';
import { Lab04EventTriggersStack } from '../lib/lab04-event-triggers-stack';
import { Lab05LambdaRdsStack } from '../lib/lab05-lambda-rds-stack';
import { Lab06Ec2WebsiteStack } from '../lib/lab06-ec2-website-stack';
import { Lab07CapstoneStack } from '../lib/lab07-capstone-stack';
import { Lab08AiBedrockStack } from '../lib/lab08-ai-bedrock-stack';

const app = new cdk.App();
const ctx = (key: string, fallback: string): string => String(app.node.tryGetContext(key) ?? fallback);

const env = { account: process.env.CDK_DEFAULT_ACCOUNT, region: process.env.CDK_DEFAULT_REGION };
const tags = { project: 'aws-foundations-labs' };
const common = { env, tags };

new Lab01StaticSiteStack(app, 'Lab01StaticSite', { ...common, description: 'Lab 01 - static website on S3 + CloudFront' });
new Lab02LambdaBasicsStack(app, 'Lab02LambdaBasics', { ...common, description: 'Lab 02 - Lambda basics' });
new Lab03ApiDynamoDbStack(app, 'Lab03ApiDynamoDb', { ...common, description: 'Lab 03 - API Gateway + Lambda + DynamoDB' });
new Lab04EventTriggersStack(app, 'Lab04EventTriggers', {
  ...common,
  description: 'Lab 04 - S3, SQS and schedule triggers',
  notificationEmail: app.node.tryGetContext('email'),
});
new Lab05LambdaRdsStack(app, 'Lab05LambdaRds', { ...common, description: 'Lab 05 - Lambda + RDS PostgreSQL' });
new Lab06Ec2WebsiteStack(app, 'Lab06Ec2Website', {
  ...common,
  description: 'Lab 06 - EC2 web servers behind a load balancer',
  repoUrl: ctx('repoUrl', 'https://github.com/YOUR-GITHUB-USER/aws-foundations-labs.git'),
});

const stage = Number(ctx('stage', '1'));
if (![1, 2, 3].includes(stage)) throw new Error(`stage must be 1, 2 or 3 (got ${stage})`);
new Lab07CapstoneStack(app, 'Lab07Capstone', { ...common, stage, description: `Lab 07 - capstone website, stage ${stage}` });

new Lab08AiBedrockStack(app, 'Lab08AiBedrock', {
  ...common,
  description: 'Lab 08 - AI answers with Amazon Bedrock',
  modelId: ctx('modelId', 'us.amazon.nova-micro-v1:0'),
  siteContext: ctx('siteContext', 'Your Name is a computer science student learning AWS.'),
});
