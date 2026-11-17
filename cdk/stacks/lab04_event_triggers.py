"""Lab 04 · Three triggers: S3 upload, SQS queue (+ DLQ), and a schedule."""

import aws_cdk as cdk
from aws_cdk import aws_events as events
from aws_cdk import aws_events_targets as targets
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_notifications as s3n
from aws_cdk import aws_sns as sns
from aws_cdk import aws_sns_subscriptions as subs
from aws_cdk import aws_sqs as sqs
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from constructs import Construct

from .shared import LabFunction


class Lab04EventTriggersStack(cdk.Stack):
    def __init__(self, scope: Construct, construct_id: str, *, notification_email: str | None = None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Shared: an SNS topic that emails you
        topic = sns.Topic(self, "Notifications", display_name="AWS Labs")
        if notification_email:
            topic.add_subscription(subs.EmailSubscription(notification_email))
        else:
            cdk.Annotations.of(self).add_warning_v2(
                "lab04:no-email", "No email given: add -c email=you@example.com to receive notifications."
            )

        # Trigger 1: S3 upload -> Lambda -> SNS
        uploads = s3.Bucket(
            self,
            "Uploads",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            enforce_ssl=True,
            removal_policy=cdk.RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )
        on_upload = LabFunction(
            self,
            "OnUpload",
            code_dir="labs/04-event-triggers/src/on-upload",
            description="Lab 04 - runs on every S3 upload",
            environment={"TOPIC_ARN": topic.topic_arn},
        )
        uploads.grant_read(on_upload)
        topic.grant_publish(on_upload)
        uploads.add_event_notification(s3.EventType.OBJECT_CREATED, s3n.LambdaDestination(on_upload))

        # Trigger 2: SQS queue -> Lambda, failed messages to a dead-letter queue
        dead_letters = sqs.Queue(self, "OrdersDlq", retention_period=cdk.Duration.days(14))
        orders = sqs.Queue(
            self,
            "Orders",
            visibility_timeout=cdk.Duration.seconds(60),
            dead_letter_queue=sqs.DeadLetterQueue(queue=dead_letters, max_receive_count=3),
        )
        process_order = LabFunction(
            self,
            "ProcessOrder",
            code_dir="labs/04-event-triggers/src/process-order",
            description="Lab 04 - processes orders from SQS",
        )
        process_order.add_event_source(
            SqsEventSource(
                orders,
                batch_size=10,
                max_batching_window=cdk.Duration.seconds(5),
                report_batch_item_failures=True,
            )
        )

        # Trigger 3: a schedule -> Lambda -> SNS
        daily_report = LabFunction(
            self,
            "DailyReport",
            code_dir="labs/04-event-triggers/src/daily-report",
            description="Lab 04 - emails a daily report",
            environment={"BUCKET_NAME": uploads.bucket_name, "TOPIC_ARN": topic.topic_arn},
            timeout=cdk.Duration.seconds(30),
        )
        uploads.grant_read(daily_report)
        topic.grant_publish(daily_report)
        events.Rule(
            self,
            "DailyReportSchedule",
            schedule=events.Schedule.cron(minute="0", hour="7"),  # 07:00 UTC every day
            targets=[targets.LambdaFunction(daily_report)],
        )

        cdk.CfnOutput(self, "UploadsBucket", value=uploads.bucket_name)
        cdk.CfnOutput(self, "OrdersQueueUrl", value=orders.queue_url)
        cdk.CfnOutput(self, "DeadLetterQueueUrl", value=dead_letters.queue_url)
