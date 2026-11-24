# Day 20: SQS, Worker Lambda & SNS Order Notifications

## 60-minute agenda
- 0–10 min — Synchronous vs asynchronous order processing
- 10–20 min — SQS Standard, visibility timeout, retries and DLQ
- 20–35 min — Console: queue + DLQ + worker trigger
- 35–50 min — SNS topic, verified subscription and full test
- 50–60 min — Idempotency, failures, recap

## Scope and instructor checklist
1. Open Day17 code and compare key functions to app/main.py.
2. Run tests first (no AWS); follow incremental AWS steps in README.
3. Demonstrate exactly the routes or worker logic for this session.
4. Record screenshots or screenshots substitute: logs, JSON and status codes.
5. If AWS billing eligibility is not clear, use only local mode.

## Console click path
### 1. Account and cost safety
Review SNS destination pricing/availability, SQS/Lambda and account limitations. No SMS. Keep trigger disabled when idle if desired; idle polling may still generate queue requests.

### 2. DLQ
SQS → Create queue → Standard → CapstoneOrdersDLQ. Create first.

### 3. Source queue
SQS → Create queue → Standard → CapstoneOrdersQueue → visibility timeout 60 s → redrive policy → CapstoneOrdersDLQ, max receives 5.

### 4. SNS
SNS → Topics → Create topic → Standard → CapstoneOrderNotifications → create email subscription to a trainer-controlled address → click confirmation email.

### 5. Worker function
Lambda → Create function → CapstoneOrderWorker → compatible Python runtime; IAM scoped role, package from scripts/build_worker_zip.py, handler worker.handler, timeout 10s; env ORDERS_TABLE, NOTIFICATION_TOPIC_ARN.

### 6. IAM
Attach AWSLambdaBasicExecutionRole and AWSLambdaSQSQueueExecutionRole; add scoped GetItem/UpdateItem on table and sns:Publish on topic. API Lambda role: scoped sqs:SendMessage.

### 7. Trigger
Lambda → Worker → Add trigger → SQS → CapstoneOrdersQueue → batch size 1 → turn on ReportBatchItemFailures in event source mapping settings if console supports it. Verify enabled state.

### 8. API env
Lambda → CapstoneOrderApi → Configuration → Environment variables → ORDER_QUEUE_URL equals source queue URL. Save and wait for update to complete.

### 9. End-to-end
POST /orders then GET repeatedly, observe status move PENDING → CONFIRMED; inspect email and CloudWatch. For broken worker, inspect DLQ after retries.

### 10. Cleanup
Leave for Day 21 only; disable/remove event-source mapping before final cleanup.


## Troubleshooting
- **SQS AccessDenied:** API Lambda role needs sqs:SendMessage scoped to queue resource.
- **Worker not triggered:** Check queue/worker Region, enabled event source mapping, worker role and queue visibility timeout.
- **SNS PendingConfirmation:** Recipient must confirm subscription; do not assume email is delivered until confirmed.
- **Repeated deliveries:** Expected with at-least-once queues; demonstrate idempotent conditional status change.
- **Messages reach DLQ:** Review worker error logs, correct error and manually decide whether to redrive.

## Expected deliverable
Explain at-least-once delivery, simulate invalid SQS JSON with tests/test_worker.py, and draw failure and retry workflow.

## Source references
- https://docs.aws.amazon.com/lambda/latest/dg/python-package.html
- https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html
- https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-errorhandling.html
- https://aws.amazon.com/free/


## Lambda build standard for this training
Use **Python 3.13 / x86_64** for both `CapstoneOrderApi` and `CapstoneOrderWorker`. API handler: `lambda_handler.handler`; worker handler: `worker.handler`. Build deployment ZIPs with the scripts in `project/scripts/` and upload only the generated ZIPs from `project/dist/`. See `project/README.md` for the exact PowerShell commands and validation checks.
