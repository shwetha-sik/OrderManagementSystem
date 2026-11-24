"""Capstone: one FastAPI app, local memory or DynamoDB, optional SQS.
Runs locally with no AWS credentials (default STORAGE_BACKEND=memory).
"""
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.store import make_store

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orders")
app = FastAPI(title="Serverless Order Management", version="1.0.0")
store = make_store()
CATALOG = {
    "PROD101": {"name": "Notebook", "price": Decimal("199.00")},
    "PROD102": {"name": "Mouse", "price": Decimal("499.00")},
    "PROD103": {"name": "Keyboard", "price": Decimal("899.00")},
    "PROD104": {"name": "USB Cable", "price": Decimal("149.00")},
    "PROD105": {"name": "Headset", "price": Decimal("1299.00")},
}

class OrderItemInput(BaseModel):
    product_id: str = Field(min_length=1)
    quantity: int = Field(ge=1, le=100)

class CreateOrderRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    items: list[OrderItemInput] = Field(min_length=1, max_length=25)

@app.get("/health")
def health():
    return {"status": "ok", "storage": os.getenv("STORAGE_BACKEND", "memory")}

@app.get("/products")
def products():
    return [{"product_id": key, "name": value["name"], "price_inr": str(value["price"])}
            for key, value in CATALOG.items()]

@app.post("/orders", status_code=201)
def create_order(payload: CreateOrderRequest):
    items=[]
    total=Decimal("0.00")
    for entry in payload.items:
        product=CATALOG.get(entry.product_id)
        if product is None:
            raise HTTPException(status_code=400, detail=f"Unknown product: {entry.product_id}")
        amount=product["price"] * entry.quantity
        total += amount
        items.append({"product_id": entry.product_id, "product_name": product["name"],
                      "quantity": entry.quantity, "unit_price": str(product["price"]),
                      "line_total": str(amount)})
    now=datetime.now(timezone.utc).isoformat()
    order={"order_id": "ORD-"+uuid4().hex[:12].upper(),"customer_id": payload.customer_id,
           "items": items,"total_amount": str(total),"currency": "INR",
           "status": "PENDING","created_at": now,"updated_at": now}
    try:
        store.put(order)
    except Exception:
        logger.exception("Order storage failed")
        raise HTTPException(status_code=503, detail="Order storage unavailable")
    # Day 20: asynchronous worker enabled only when ORDER_QUEUE_URL is configured.
    queue_url=os.getenv("ORDER_QUEUE_URL")
    if queue_url:
        try:
            import boto3
            boto3.client("sqs").send_message(QueueUrl=queue_url,
                MessageBody=__import__("json").dumps({"order_id": order["order_id"]}))
        except Exception:
            logger.exception("Order saved but queue publish failed: %s", order["order_id"])
            # Educational MVP: client gets 503 while record remains PENDING.
            # Real production system requires an outbox/reconciliation mechanism.
            raise HTTPException(status_code=503,
                detail={"message":"Order saved, but processing was not queued", "order_id":order["order_id"]})
    return order

@app.get("/orders")
def list_orders():
    try:
        return store.list_all(limit=25)
    except Exception:
        logger.exception("List orders failed")
        raise HTTPException(status_code=503,detail="Order storage unavailable")

@app.get("/orders/{order_id}")
def get_order(order_id: str):
    try:
        order=store.get(order_id)
    except Exception:
        logger.exception("Get order failed")
        raise HTTPException(status_code=503,detail="Order storage unavailable")
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.patch("/orders/{order_id}/cancel")
def cancel_order(order_id: str):
    try:
        return store.transition(order_id, from_status="PENDING", to_status="CANCELLED")
    except KeyError:
        raise HTTPException(status_code=404, detail="Order not found")
    except ValueError:
        raise HTTPException(status_code=409, detail="Order cannot be cancelled")
    except Exception:
        logger.exception("Cancel order failed")
        raise HTTPException(status_code=503, detail="Order storage unavailable")
