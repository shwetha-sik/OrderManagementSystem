# AWS Developer capstone — Serverless Order Management System

This source is cumulative for Days 18–21 and **continues the Day 17 FastAPI application**.

## Quick start (no AWS account needed)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:STORAGE_BACKEND="memory"
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000/docs, create an order then test GET and cancel.
In a second terminal, run `python -m pytest -q` (run from repository root).

## Switch to DynamoDB (Day 18)

Only after checking AWS account Free Tier/credits and enabling budget safeguards:
1. Create `CapstoneOrders` table, partition key `order_id` (String), in one selected Region. Prefer eligible provisioned settings or local fallback; do not assume free usage.
2. Give the Lambda execution role scoped dynamodb:GetItem, PutItem, UpdateItem, Scan on this table, plus AWSLambdaBasicExecutionRole. Do not assign AdministratorAccess.
3. Set `STORAGE_BACKEND=dynamodb`, `ORDERS_TABLE=CapstoneOrders`, `AWS_REGION=ap-south-1` (choose your actual Region). Locally ensure AWS CLI profile is configured (`aws sts get-caller-identity`).
4. Run API again. Order data now persists across restarts.

## Lambda (Day 18)

Handler `lambda_handler.handler`, Python runtime compatible with installed deps, x86_64; select timeout ~10s and memory ~128 MB for small demo. Use `python scripts/build_lambda_zip.py` on **Linux / WSL / compatible environment** to bundle third-party dependencies and app. Upload `dist/order_api_lambda.zip` to Lambda. Do not depend on Windows-built binary wheels for a Linux Lambda runtime.

## API Gateway HTTP API (Day 19)

Create HTTP API, Lambda integration to order-api function, routes `ANY /{proxy+}` and `GET /health` (or `$default` route) and stage `$default` auto-deploy; API Gateway must have permission to invoke Lambda (console usually adds it). Set a suitable authorization configuration before public production use; demo URL can be temporarily public but do not expose private data.

Invoke `https://YOUR_API_ID.execute-api.REGION.amazonaws.com/health` and `.../orders`.

## SQS + Worker + SNS (Day 20)

1. Create `CapstoneOrdersDLQ` (Standard) and `CapstoneOrdersQueue` (Standard) in same Region; enable redrive policy to DLQ, maxReceiveCount=5. Set visibility timeout e.g. 60s for worker Lambda timeout 10s.
2. Create SNS standard topic `CapstoneOrderNotifications`. Subscribe ONLY verified trainer-controlled email, click confirmation link; check email delivery usage and eligibility.
3. Set API Lambda env `ORDER_QUEUE_URL` to queue URL. Grant scoped `sqs:SendMessage` on only this queue.
4. Create worker Lambda using `python scripts/build_worker_zip.py`, handler `worker.handler`, env `ORDERS_TABLE` and `NOTIFICATION_TOPIC_ARN`, role includes AWSLambdaBasicExecutionRole, AWSLambdaSQSQueueExecutionRole, DynamoDB GetItem/UpdateItem, SNS Publish for only this topic.
5. Add SQS trigger to worker, batch size 1 for live demo, turn on **ReportBatchItemFailures** if available in console/event-source mapping. Confirm queue source + worker same Region.
6. Create order using POST; API writes PENDING then enqueues order ID; worker transitions to CONFIRMED and sends SNS notification. If SQS disabled, local CRUD continues to work.

**MVP caveats:** If SQS publish fails after the order is saved, API returns 503 with order ID; record remains PENDING. If SNS fails after the CONFIRMED update, notification may not be retried. Production needs outbox/reconciliation, authorization, stronger duplicate-request protection, GSI/pagination, secrets and end-to-end trace correlation. Avoid portraying this tutorial as production-ready.

## Day 21 validation

Run `python -m pytest -q`, use Postman collection, inspect Lambda CloudWatch log groups, inspect SQS metrics/DLQ, confirm IAM deny permissions on unauthorized resources. Demo invalid quantity 422, unknown product 400, non-existent order 404, repeated cancel 409, normal order CONFIRMED and notification.


## Lambda build target — Python 3.13 / x86_64 (verified configuration)

The training environment used for this capstone has been successfully deployed with:
- Lambda runtime: **Python 3.13**
- Architecture: **x86_64**
- API handler: `lambda_handler.handler`
- Worker handler: `worker.handler`

Build dependencies for the Linux Lambda environment even when the trainer uses Windows. The build scripts download binary wheels for the selected Lambda Python ABI and architecture; they do not package Windows-native extensions.

### Windows PowerShell — API Lambda package

Run from the `project` directory:

```powershell
$env:LAMBDA_PYTHON_VERSION="3.13"
$env:LAMBDA_ARCH="x86_64"
python -m pip install --upgrade pip
python scripts/build_lambda_zip.py
```

Upload the generated file from `project/dist/` whose name starts with `order_api_lambda_py3.13_x86_64` to the existing `CapstoneOrderApi` Lambda. Keep handler `lambda_handler.handler`.

### Windows PowerShell — SQS worker package

Run from the same `project` directory:

```powershell
$env:LAMBDA_PYTHON_VERSION="3.13"
$env:LAMBDA_ARCH="x86_64"
python -m pip install --upgrade pip
python scripts/build_worker_zip.py
```

Upload the generated `worker_lambda_py3.13_x86_64.zip` to `CapstoneOrderWorker`. Keep handler `worker.handler`.

### AWS Console runtime checks

For each Lambda, open **Lambda → Functions → function name → Code → Runtime settings** and confirm Python 3.13. Open **Configuration → General configuration → Edit** and confirm x86_64 architecture. The package target must match both settings exactly. Do not upload a package built for Python 3.12/3.14 or arm64 to this function.

The API package includes pinned FastAPI, Pydantic, Mangum and boto3 dependencies. The worker package includes pinned boto3. The API build script validates that `pydantic_core` contains a Linux `.so` extension for the selected Python ABI and architecture before creating the ZIP. It also checks the final archive layout and excludes Python cache files.

**Important:** Upload the generated deployment ZIP from `project/dist/`, not the complete trainer-kit ZIP. If the build validation fails, do not upload the artifact. Re-run with the exact runtime/architecture configured in Lambda and inspect the pip error.


## Cleanup

Remove HTTP API/stages and Lambda integrations; delete event-source mapping; delete both Lambda functions; delete SQS source and DLQ; delete SNS topic/subscription; delete DynamoDB table; remove custom IAM roles/policies; remove training CloudWatch log groups if safe. Confirm Billing > Free Tier and Cost Explorer/Budgets afterward (data may be delayed). Do not delete shared or non-training resources.

## Local-only fallback

For restricted/free accounts, run API in `memory` mode plus `pytest`. To show Lambda events, import `worker.py` and invoke with the sample `events/sqs_event.json` after replacing order ID; use tests/test_worker.py mock for no-AWS example. Offline API Gateway routing is simulated by FastAPI/Swagger UI; state clearly this is a functional simulation, not an actual AWS deployment.
