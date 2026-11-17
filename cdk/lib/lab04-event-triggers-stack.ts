import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as s3n from 'aws-cdk-lib/aws-s3-notifications';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subs from 'aws-cdk-lib/aws-sns-subscriptions';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import { LabFunction } from './shared';

export interface Lab04Props extends cdk.StackProps {
  /** Email for SNS notifications (cdk deploy -c email=you@example.com) */
  readonly notificationEmail?: string;
}

/** Lab 04 · Three triggers: S3 upload, SQS queue (+ DLQ), and a schedule. */
export class Lab04EventTriggersStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: Lab04Props = {}) {
    super(scope, id, props);

    // Shared: an SNS topic that emails you
    const topic = new sns.Topic(this, 'Notifications', { displayName: 'AWS Labs' });
    if (props.notificationEmail) {
      topic.addSubscription(new subs.EmailSubscription(props.notificationEmail));
    } else {
      cdk.Annotations.of(this).addWarningV2('lab04:no-email', 'No email given: add -c email=you@example.com to receive notifications.');
    }

    // Trigger 1: S3 upload → Lambda → SNS
    const uploads = new s3.Bucket(this, 'Uploads', {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: true,
    });
    const onUpload = new LabFunction(this, 'OnUpload', {
      codeDir: 'labs/04-event-triggers/src/on-upload',
      description: 'Lab 04 - runs on every S3 upload',
      environment: { TOPIC_ARN: topic.topicArn },
    });
    uploads.grantRead(onUpload);
    topic.grantPublish(onUpload);
    uploads.addEventNotification(s3.EventType.OBJECT_CREATED, new s3n.LambdaDestination(onUpload));

    // Trigger 2: SQS queue → Lambda, failed messages to a dead-letter queue
    const deadLetters = new sqs.Queue(this, 'OrdersDlq', { retentionPeriod: cdk.Duration.days(14) });
    const orders = new sqs.Queue(this, 'Orders', {
      visibilityTimeout: cdk.Duration.seconds(60),
      deadLetterQueue: { queue: deadLetters, maxReceiveCount: 3 },
    });
    const processOrder = new LabFunction(this, 'ProcessOrder', {
      codeDir: 'labs/04-event-triggers/src/process-order',
      description: 'Lab 04 - processes orders from SQS',
    });
    processOrder.addEventSource(new SqsEventSource(orders, {
      batchSize: 10,
      maxBatchingWindow: cdk.Duration.seconds(5),
      reportBatchItemFailures: true,
    }));

    // Trigger 3: a schedule → Lambda → SNS
    const dailyReport = new LabFunction(this, 'DailyReport', {
      codeDir: 'labs/04-event-triggers/src/daily-report',
      description: 'Lab 04 - emails a daily report',
      environment: { BUCKET_NAME: uploads.bucketName, TOPIC_ARN: topic.topicArn },
      timeout: cdk.Duration.seconds(30),
    });
    uploads.grantRead(dailyReport);
    topic.grantPublish(dailyReport);
    new events.Rule(this, 'DailyReportSchedule', {
      schedule: events.Schedule.cron({ minute: '0', hour: '7' }), // 07:00 UTC every day
      targets: [new targets.LambdaFunction(dailyReport)],
    });

    new cdk.CfnOutput(this, 'UploadsBucket', { value: uploads.bucketName });
    new cdk.CfnOutput(this, 'OrdersQueueUrl', { value: orders.queueUrl });
    new cdk.CfnOutput(this, 'DeadLetterQueueUrl', { value: deadLetters.queueUrl });
  }
}
