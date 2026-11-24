"""SQS event source: partial batch failures, idempotent status transition."""
import json
import logging
import os
from app.store import DynamoStore

logger=logging.getLogger(__name__)

def handler(event, context):
    store=DynamoStore()
    failures=[]
    for rec in event.get("Records",[]):
        msg_id=rec.get("messageId", "missing")
        try:
            payload=json.loads(rec["body"])
            order_id=payload["order_id"]
            record=store.get(order_id)
            if record is None:
                raise ValueError(f"Unknown order ID: {order_id}")
            if record["status"] in ("CONFIRMED","CANCELLED"):
                logger.info("Skipping already-finalized order %s",order_id)
                continue
            try:
                updated=store.transition(order_id,"PENDING","CONFIRMED")
            except ValueError:
                logger.info("Order already handled in competing worker: %s",order_id)
                continue
            topic_arn=os.getenv("NOTIFICATION_TOPIC_ARN")
            if topic_arn:
                import boto3
                try:
                    boto3.client("sns").publish(TopicArn=topic_arn,
                      Subject="Order confirmed",
                      Message=f"Order {order_id} is {updated['status']}")
                except Exception:
                    # Documented MVP limitation: confirmation is committed before SNS.
                    # Requires outbox + retry for guaranteed notification delivery.
                    logger.exception("Notification failed after confirmation for %s",order_id)
        except Exception:
            logger.exception("SQS processing failed: %s",msg_id)
            failures.append({"itemIdentifier":msg_id})
    return {"batchItemFailures":failures}
