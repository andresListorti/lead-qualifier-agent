"""AWS Lambda entrypoint: wraps the FastAPI app for API Gateway (HTTP API v2)."""

from mangum import Mangum

from api.app.main import app

handler = Mangum(app, lifespan="off")
