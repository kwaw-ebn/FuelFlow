# FuelFlow Ghana

Fuel station management built with Next.js, TypeScript, FastAPI and PostgreSQL. This repository is the first working increment of the attached master specification, **not a completed production system**.

## Implemented

- Owner installation through a password-prompting CLI; no public signup or default password.
- Password hashing using scrypt, 30-minute JWT sessions, account status enforcement.
- Owner, manager, supervisor, attendant, accountant and auditor permissions; station access checks.
- Station and staff creation; products, tanks and nozzles.
- Shift opening with a fixed fuel-price snapshot; attendant assignment checks.
- Meter submission and cash, Mobile Money and card collection reconciliation.
- Transactional reconciliation with PostgreSQL row locks; duplicate submission prevention; tank capacity and stock checks.
- Delivery reference uniqueness and stock posting; expenses; basic daily dashboard and low-stock alerts.
- Append-only audit API workflow (owner read access); responsive browser UI; OpenAPI at `/docs`.

Payments are staff-confirmed records. No gateway or hardware connection is implemented. Stock is updated when a supervisor reconciles a shift; therefore stock during an open shift remains an estimate. Dashboard dates use UTC (Ghana local time). Expenses use recording date; dashboard shifts use opening date.

## Local setup

Python 3.12+ and Node 22+ recommended.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m app.manage migrate
python -m app.manage owner --email owner@example.com --name "Station Owner"
uvicorn app.main:app --reload
```

For local development, unset DATABASE_URL to use SQLite. PostgreSQL is required for concurrent financial operations because SQLite does not provide the PostgreSQL row-lock semantics used here.

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000. Sign in, create a station, products, tanks, nozzles and attendants, then open a shift. IDs are displayed in Inventory; staff IDs can be retrieved through authenticated `GET /staff?station_id=...` in the API docs. The current UI requires entering these IDs manually.

## Render and Neon

1. Create a dedicated Neon PostgreSQL project. Copy its SSL connection URL into Render's `DATABASE_URL` secret. Never commit the connection string.
2. Connect this repository to Render using `render.yaml`. Review the instance plans and costs before provisioning.
3. Set API `CORS_ORIGINS` to the exact frontend HTTPS origin. Set frontend `NEXT_PUBLIC_API_URL` to the API HTTPS origin **before building**.
4. In the backend environment, run `python -m app.manage migrate`, then create the owner with the interactive CLI. Use a secure shell or local environment with authorized database access; never put the password in a build command.
5. Restart services and verify `/health`, login and a complete test shift against a non-production database.

The `migrate` command creates an initial schema only. Versioned Alembic upgrades must be added before changing a deployed schema. Render configuration is supplied; services and database have not been provisioned by this repository.

## Validation

```bash
cd backend
pytest -q
```

## Remaining master-prompt work

See [requirements](docs/REQUIREMENTS.md) for the full intended product. The next increments must add historical price editing, separate pump records, richer shift scheduling/handover, individual payment references and approved credit, dip readings and stock reconciliation, delivery approval/attachments, customer credit and fleet ledgers, expense approvals, daily close/reopening, incidents/maintenance, downloadable reports, password reset, owner 2FA, rate limiting, secure uploads, PWA/offline support, demo seeding and full dashboard analytics.

Before live use: add database-level financial constraints and active-shift uniqueness, handle concurrent unique conflicts as 409 responses, add versioned migrations, protect audit records with a separate restricted DB role/immutable archive, add rate limiting and monitoring, restrict public API documentation if required, establish tested backup/restore, pin and scan dependencies, and complete PostgreSQL concurrency and end-to-end tests. Current tests use isolated SQLite databases and do not certify concurrent production posting.
