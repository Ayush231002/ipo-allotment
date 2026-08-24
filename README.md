# AllotCheck

Check IPO allotment status across registrars — all your PANs in one click.

Supports **KFintech** and **MUFG / Intime** today, and is built so new
registrars plug in with a single small file. No login, no CAPTCHA, and no
PAN is ever stored on a server (the PAN list lives only in the user's browser).

---

## Project structure

```
allotcheck/
├── web/                        # Frontend — static site (→ S3 + CloudFront)
│   ├── index.html
│   └── assets/
│       ├── styles.css          # design system (light + dark)
│       ├── app.js              # UI logic; talks to /api/*
│       └── config.js           # apiBase (empty = same origin)
│
├── backend/                    # API — Python, standard library only (→ AWS Lambda)
│   ├── lambda_function.py      # AWS Lambda entry (handler = lambda_function.handler)
│   ├── local_server.py         # run the whole app locally for dev/testing
│   ├── core.py                 # framework-agnostic router (tested once, used by both)
│   └── registrars/             # one adapter per registrar
│       ├── base.py             # RegistrarAdapter interface + helpers
│       ├── kfintech.py
│       ├── mufg.py
│       └── __init__.py         # registry — add new registrars here
│
├── infra/                      # AWS infrastructure-as-code (added at deploy time)
├── docs/
│   └── ARCHITECTURE.md
└── README.md
```

---

## Run locally

```bash
cd backend
python local_server.py
```

Opens `http://localhost:8080/`. The dev server serves the frontend **and** the
API, exactly like the AWS setup, so what you see locally is what ships.

Requires Python 3.9+ (standard library only — nothing to `pip install`).

---

## API

| Method & path | Returns |
|---|---|
| `GET /api/registrars` | `[{key,label,note}]` — drives the UI's switcher |
| `GET /api/<key>/companies` | `[{id,name}]` — live IPO list for that registrar |
| `GET /api/<key>/check?clientid=<id>&pan=<PAN>` | normalized allotment result |
| `POST /api/track` | records one anonymous analytics event (never a PAN) |
| `GET /api/admin/stats?token=<t>&days=<n>` | aggregate stats for the admin dashboard (token-protected) |

Normalized result: `{found, name, applied, allotted, category, refund, account}`
(or `{error}`). Each registrar fills the fields it exposes; the rest stay blank.

---

## Admin dashboard

Open **`/admin`** and enter the admin token. It shows traffic (page views,
unique visitors, trend), locations, devices, checks run, PANs checked,
**registrar health** (a rising busy/error rate is an early warning that a
registrar may be rate-limiting/blocking us), and the most-checked IPOs.

- Set the token via env var **`ALLOTCHECK_ADMIN_TOKEN`** (dev default: `changeme`
  — change it before deploying).
- **Privacy:** only anonymous aggregate counters are stored — never a PAN,
  name, or any personal data.
- **Storage:** local dev writes `backend/.data/analytics.json`. AWS Lambda's
  filesystem is ephemeral, so swap the store for DynamoDB at deploy time (see
  `backend/analytics.py` and `docs/ARCHITECTURE.md`).

---

## Add a new registrar

1. Create `backend/registrars/<name>.py` subclassing `RegistrarAdapter`;
   implement `list_companies()` and `check(client_id, pan)`.
2. Register it in `backend/registrars/__init__.py` (one line).

That's it — the API route and the UI switcher pick it up automatically.

> If a registrar requires a CAPTCHA, it must stay human-in-the-loop (the user
> solves it); this project never auto-solves or bypasses CAPTCHAs.

---

## Deployment (overview)

Serverless, so the bill is near-zero when idle:

- **Frontend** → Amazon S3 (static hosting) behind **CloudFront** (CDN + HTTPS).
- **Backend** → **AWS Lambda** + **API Gateway**, with CloudFront routing
  `/api/*` to the API so the frontend can use relative paths (no CORS).

The exact IaC/console steps live in `infra/` and are added when you're ready to
deploy. See `docs/ARCHITECTURE.md` for the cost model and rationale.
