"""Memory and DynamoDB stores with the same small interface."""
import os
from datetime import datetime,timezone

class MemoryStore:
    def __init__(self): self.orders={}
    def put(self, order): self.orders[order["order_id"]] = dict(order)
    def get(self, order_id):
        order=self.orders.get(order_id)
        return dict(order) if order else None
    def list_all(self,limit=25): return list(self.orders.values())[:limit]
    def transition(self,order_id,from_status,to_status):
        order=self.orders.get(order_id)
        if order is None: raise KeyError(order_id)
        if order["status"]!=from_status: raise ValueError("Unexpected status")
        order["status"]=to_status
        order["updated_at"]=datetime.now(timezone.utc).isoformat()
        return dict(order)

class DynamoStore:
    def __init__(self):
        import boto3
        self.table=boto3.resource("dynamodb").Table(os.getenv("ORDERS_TABLE","CapstoneOrders"))
    def put(self,order):
        self.table.put_item(Item=order,ConditionExpression="attribute_not_exists(order_id)")
    def get(self,order_id):
        return self.table.get_item(Key={"order_id":order_id},ConsistentRead=True).get("Item")
    def list_all(self,limit=25):
        # Tutorial scale only. Production: model query access patterns and paginate.
        return self.table.scan(Limit=limit).get("Items",[])
    def transition(self,order_id,from_status,to_status):
        from botocore.exceptions import ClientError
        try:
            r=self.table.update_item(Key={"order_id":order_id},
              UpdateExpression="SET #s=:new, updated_at=:updated",
              ConditionExpression="attribute_exists(order_id) AND #s=:old",
              ExpressionAttributeNames={"#s":"status"},
              ExpressionAttributeValues={":new":to_status, ":old":from_status,
                ":updated":datetime.now(timezone.utc).isoformat()},
              ReturnValues="ALL_NEW")
            return r["Attributes"]
        except ClientError as exc:
            if exc.response["Error"]["Code"]=="ConditionalCheckFailedException":
                if self.get(order_id) is None: raise KeyError(order_id) from exc
                raise ValueError("Unexpected status") from exc
            raise

def make_store():
    backend=os.getenv("STORAGE_BACKEND","memory").lower()
    if backend=="dynamodb": return DynamoStore()
    if backend=="memory": return MemoryStore()
    raise ValueError("STORAGE_BACKEND must be memory or dynamodb")
