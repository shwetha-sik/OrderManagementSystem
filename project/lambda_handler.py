"""AWS Lambda HTTP API entrypoint; handler is lambda_handler.handler."""
from mangum import Mangum
from app.main import app
handler = Mangum(app, lifespan="off")
