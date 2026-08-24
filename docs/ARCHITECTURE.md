# Architecture

## Goals
- **Public, always-on** tool that stays cheap when idle and absorbs spikes on
  IPO allotment days.
- **Extensible**: adding a registrar is one adapter file.
- **Privacy-first**: no PAN is stored server-side; the saved list lives only in
  the user's browser (localStorage), with a Backup/Restore file for portability.

## High level

```
          ┌────────────────────────── CloudFront (CDN, HTTPS) ─────────────────────────┐
Browser → │  default behaviour  → S3 bucket (index.html, assets)  [static frontend]     │
          │  /api/*  behaviour  → API Gateway → Lambda (Python)   [registrar adapters]  │
          └────────────────────────────────────────────────────────────────────────────┘
                                                    │
                                                    └── outbound HTTPS → registrar sites
                                                        (KFintech, MUFG, …)
```

Because `/api/*` is served from the **same CloudFront domain** as the frontend,
the browser makes same-origin calls — no CORS configuration needed.

## Why serverless (cost)
- **Lambda**: billed per request + duration. At low/idle traffic this is
  effectively free (generous free tier), and it scales to zero — no server to
  keep running.
- **API Gateway**: per-request pricing; negligible at small scale.
- **S3 + CloudFront**: fractions of a rupee for a tiny static site; CloudFront
  caches assets at the edge so S3 is barely hit.
- **No VPC / no NAT gateway**: the Lambda runs outside a VPC so it has direct
  internet access to the registrar sites. (A NAT gateway is the usual surprise
  cost in serverless setups — avoided here.)

Rough idle cost target: **well under ₹100/month** for modest traffic; the
biggest lever is Lambda invocation count on allotment days.

## Backend design
- `core.handle_api(path, params) -> (status, obj)` is the single source of
  truth. `lambda_function.py` (AWS) and `local_server.py` (dev) are thin
  adapters over it, so behaviour is identical locally and in production.
- Standard-library only → tiny deploy artifact, fast cold starts, no dependency
  management.
- Per-registrar **in-memory TTL cache** (e.g. KFintech company list) lives on
  the warm Lambda container to cut repeat upstream calls.

## Extensibility
Each registrar implements `RegistrarAdapter` (`list_companies`, `check`) and
returns a **normalized result**, so the frontend renders every registrar with
one table. Registrars can expose different fields (name, category, refund, DP
ID) — missing ones simply render blank.

## Anti-blocking strategy (important for a public tool)

At public scale, the biggest risk is a registrar rate-limiting or blocking us,
because a public proxy funnels *everyone's* requests through one server IP —
which looks like a scraper. Mitigations, by registrar:

- **CORS-open registrars (e.g. KFintech)** → checked **client-side, directly
  from each user's browser** (`direct_info()` on the adapter tells the frontend
  the live API URL). Traffic is spread across thousands of user IPs instead of
  our one server IP. The server only serves the (cached) company list, and
  remains a fallback if the direct call fails.
- **CORS-closed registrars (e.g. MUFG, behind Akamai)** → must be proxied, so:
  - company lists are **cached** (TTL) to cut upstream calls;
  - upstream calls are **serialised + throttled** (`MIN_INTERVAL`) per process;
  - `403/429/503/5xx` are surfaced as a friendly **"registrar busy"** state
    with a link to the registrar's own page — the product degrades gracefully
    instead of erroring out.

  **Global throttling in AWS:** the per-process throttle only limits one warm
  Lambda container. To cap *total* upstream pressure, set the Lambda's
  **reserved concurrency** low (e.g. 2–5) and add an **API Gateway usage plan**
  (or WAF rate rule). This is the real lever and belongs in `infra/`.

  Residual risk is real: a registrar behind enterprise bot-management can still
  block a datacenter proxy. This is a product/legal risk to accept knowingly,
  not something code fully eliminates.

## Analytics & admin dashboard

A privacy-first, self-owned analytics layer (`backend/analytics.py`) records
only **anonymous aggregate counters** — page views, unique daily visitors,
checks run, PANs checked, country (from CloudFront's `CloudFront-Viewer-Country`
header — free geo), device, per-registrar result tallies, and top IPOs. **No
PAN, name, or personal data is ever stored.** The `/admin` dashboard reads
`/api/admin/stats` (token via `ALLOTCHECK_ADMIN_TOKEN`).

- **Registrar health** (busy/error rate per registrar) is the key product
  signal — it's an early warning that a registrar may be rate-limiting/blocking
  the server, tying directly into the anti-blocking strategy above.
- **Storage in AWS:** the local JSON store does not survive Lambda's ephemeral
  filesystem. Swap `_load`/`_save` in `analytics.py` for **DynamoDB** (a single
  table keyed by day, using atomic `ADD` updates for counters and small maps for
  country/device/registrar/IPO breakdowns). Pay-per-request DynamoDB keeps this
  near-free at low traffic.
- **Optional:** for accurate raw traffic/geo without any maintenance, also add a
  privacy-friendly tag like Cloudflare Web Analytics (free) — it complements the
  product-specific metrics the custom dashboard provides.
- **Before launch:** change `ALLOTCHECK_ADMIN_TOKEN` from the default, and
  consider stronger admin auth (e.g. Cognito) if more than one person needs
  access. Add a short **Privacy Policy** page (required for a public site that
  collects even anonymous analytics under India's DPDP / GDPR norms).

## Things to add before/at launch
- Basic rate limiting / abuse protection at API Gateway (usage plan or WAF).
- Lightweight request throttling per client (the UI already paces requests).
- Optional: a small cache layer (CloudFront cache policy) for `companies`.
- CAPTCHA-based registrars, if added, must remain human-in-the-loop.
