# infra/

AWS infrastructure-as-code goes here (added when you're ready to deploy).

Planned contents (not created yet, per current scope):
- `template.yaml` — AWS SAM template defining:
  - Lambda function (`../backend`, handler `lambda_function.handler`, no VPC)
  - HTTP API (API Gateway) with routes proxied to the Lambda
  - S3 bucket for the static site (`../web`)
  - CloudFront distribution: default → S3, `/api/*` → API Gateway
- `samconfig.toml` — deploy parameters (region `ap-south-1`, stack name, etc.)
- Deploy notes / commands.

Nothing in here affects local development — `backend/local_server.py` runs the
whole app without any AWS resources.
