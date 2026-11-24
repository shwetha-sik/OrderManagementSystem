import os
os.environ["STORAGE_BACKEND"]="memory"
os.environ.pop("ORDER_QUEUE_URL",None)
from fastapi.testclient import TestClient
from app.main import app,store

client=TestClient(app)

def payload(): return {"customer_id":"CUST001","items":[{"product_id":"PROD101","quantity":2}]}

def test_health(): assert client.get("/health").json()["status"]=="ok"

def test_product_catalog(): assert len(client.get("/products").json())==5

def test_create_get_and_cancel():
    r=client.post("/orders",json=payload()); assert r.status_code==201
    order=r.json(); assert order["total_amount"]=="398.00"
    assert client.get("/orders/"+order["order_id"]).status_code==200
    assert client.patch("/orders/"+order["order_id"]+"/cancel").json()["status"]=="CANCELLED"
    assert client.patch("/orders/"+order["order_id"]+"/cancel").status_code==409

def test_invalid_quantity():
    x=payload();x["items"][0]["quantity"]=0
    assert client.post("/orders",json=x).status_code==422

def test_unknown_product():
    x=payload();x["items"][0]["product_id"]="NOPE"
    assert client.post("/orders",json=x).status_code==400

def test_missing_order(): assert client.get("/orders/UNKNOWN").status_code==404
