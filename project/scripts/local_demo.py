"""No AWS calls: demonstrate API and synchronous worker behavior."""
import os,json
os.environ["STORAGE_BACKEND"]="memory"
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
r=c.post("/orders",json={"customer_id":"CUST001","items":[{"product_id":"PROD101","quantity":2}]})
print("POST",r.status_code,r.json())
order_id=r.json()["order_id"]
print("GET",c.get(f"/orders/{order_id}").json())
