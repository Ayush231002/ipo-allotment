// Runtime configuration.
// Locally and behind CloudFront (with /api/* routed to Lambda) this stays "".
// For a split-origin deploy, set this to your API Gateway base URL, e.g.
// window.APP_CONFIG = { apiBase: "https://abc123.execute-api.ap-south-1.amazonaws.com" };
window.APP_CONFIG = { apiBase: "" };
