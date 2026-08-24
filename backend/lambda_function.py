"""
AWS Lambda entry point (behind API Gateway HTTP API or REST API).

Deploy this `backend/` folder as the function package with handler:
    lambda_function.handler

Standard library only, so the zip is tiny and cold starts are fast. Keep the
function OUTSIDE a VPC so it has direct internet access to the registrar sites
(no NAT gateway cost). API Gateway must allow POST for /api/track.
"""
import base64
import json

from core import handle_api


def handler(event, context):
    method = (event.get("requestContext", {}).get("http", {}).get("method")
              or event.get("httpMethod") or "GET")
    path = event.get("rawPath") or event.get("path") or "/"
    params = {k: v for k, v in (event.get("queryStringParameters") or {}).items()}
    headers = event.get("headers") or {}
    body = event.get("body")
    if event.get("isBase64Encoded") and body:
        try:
            body = base64.b64decode(body).decode("utf-8", "ignore")
        except Exception:
            pass

    status, resp = handle_api(method, path, params, headers, body)
    # The SPA is served from the SAME CloudFront domain as this API, so no CORS
    # header is needed. The old wildcard `Access-Control-Allow-Origin: *` let any
    # site drive the API — removed. For a split-origin deploy, echo a single
    # allow-listed origin here instead of "*".
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
        },
        "body": json.dumps(resp),
    }
