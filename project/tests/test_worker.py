import json
from unittest.mock import patch
import worker
from app.store import MemoryStore

def test_worker_confirms_and_skips_duplicate():
    fake=MemoryStore()
    fake.put({"order_id":"ORD-TEST","status":"PENDING"})
    event={"Records":[{"messageId":"m1","body":json.dumps({"order_id":"ORD-TEST"})}]}
    with patch.object(worker,"DynamoStore",return_value=fake):
        assert worker.handler(event,None)=={"batchItemFailures":[]}
        assert fake.get("ORD-TEST")["status"]=="CONFIRMED"
        assert worker.handler(event,None)=={"batchItemFailures":[]}

def test_bad_message_is_partial_failure():
    with patch.object(worker,"DynamoStore",return_value=MemoryStore()):
        result=worker.handler({"Records":[{"messageId":"bad1","body":"not-json"}]},None)
    assert result=={"batchItemFailures":[{"itemIdentifier":"bad1"}]}
