from api.lambda_handler import handler


def http_event(path: str) -> dict:
    """Minimal API Gateway HTTP API (payload v2) event."""
    return {
        "version": "2.0",
        "routeKey": "ANY /{proxy+}",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": "example.execute-api.us-east-1.amazonaws.com"},
        "requestContext": {
            "http": {
                "method": "GET", "path": path, "protocol": "HTTP/1.1",
                "sourceIp": "127.0.0.1", "userAgent": "pytest",
            },
        },
        "isBase64Encoded": False,
    }


def test_lambda_handler_serves_health():
    response = handler(http_event("/health"), None)
    assert response["statusCode"] == 200
    assert "DEMO DATA" in response["body"]


def test_lambda_handler_protects_leads():
    response = handler(http_event("/leads"), None)
    assert response["statusCode"] in (401, 503)
