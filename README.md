# FuelFlow Ghana

A working fuel-station control system with Next.js, TypeScript, FastAPI and PostgreSQL. Version 0.2 adds commercial credit, management reports, business-day close, maintenance and security controls. The full longer-term product specification remains in [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md).

## What works

| Area | Implemented workflow |
| --- | --- |
| Access | Owner, manager, supervisor, attendant, accountant and auditor; station isolation and attendant-only shift records |
| Infrastructure | Stations, fuel products, tanks, nozzles, physical tank readings and owner-authorized stock adjustments |
| Pricing | Audited owner-only price changes and price history; opening a shift captures its fuel price |
| Shifts | Open, submit and reconcile; meter validation, payment variance, stock posting and locked reconciled shifts |
| Deliveries | Verified quantities, unique delivery references, capacity checks and transactional stock posting |
| Credit | Approved customer limits, terms, fleet vehicles, daily vehicle limits, credit charges, partial repayments, FIFO allocations, balances and overdue alerts |
| Expenses | Pending expense entry and owner or separate-manager approval; repairs generate linked expense entries |
| Close | Readiness checks, fresh closing dips, outstanding-shift checks, pending-expense checks, immutable close snapshots and owner reopening with a reason |
| Maintenance | Equipment register, fault jobs, repair completion, next-service dates and linked nozzle lockout |
| Incidents | Staff reporting, severity and resolution |
| Reports | Daily, sales, inventory, expenses, deliveries, credit balances, maintenance and estimated management margin; date and sales filters; CSV, XLSX and PDF exports |
| Security | Scrypt passwords, database-backed revocable sessions, 15-minute idle timeout, 30-minute absolute expiry, persistent login limits, owner TOTP enrollment, encrypted MFA secrets, hashed one-time recovery codes and staff disabling/password reset |
| Audit | Owner audit viewer; database triggers prevent normal UPDATE/DELETE of audit, close-event, stock, credit, payment-allocation and price-history records |

Mobile Money and card entries remain **staff-confirmed payment records**. There is no payment-gateway or pump-hardware integration.

## Run locally

Use Python 3.12 and Node 22. PostgreSQL is required for concurrent financial posting; SQLite is suitable only for local single-user development and functional tests.

```bash
cd backend
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export MFA_ENCRYPTION_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
python -m app.manage migrate
python -m app.manage owner --email owner@example.com --name "Station Owner"
python -m uvicorn app.main:app --reload
```

Owner creation prompts for a password. It does not install a default password or demo records. To use the browser installation screen instead, set a private `BOOTSTRAP_TOKEN` of at least 32 characters before starting the backend.

In another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Create a station under Settings, then register products, tanks, nozzles and staff. Open a shift, enter credit sales if needed, submit meter readings/collections and approve reconciliation. Record verified deliveries, expenses and closing dips before closing the day.

For an existing installation, retain its database and run `python -m app.manage migrate`. The migration command recognizes the exact unversioned v0.1 table set, stamps its baseline and upgrades it. Back up a live database before upgrading. Schema upgrades are versioned in `backend/migrations`; destructive downgrades are deliberately unavailable.

## Render + Neon

[Deployment instructions](docs/DEPLOYMENT.md) cover the two free-plan Render services and a dedicated Neon PostgreSQL database. `render.yaml` includes automatic schema migration, readiness checking, production MFA enforcement and generated installation/security secrets.

[Open the Render Blueprint](https://dashboard.render.com/blueprint/new?repo=https://github.com/kwaw-ebn/FuelFlow).

The Blueprint requires the Neon `DATABASE_URL`, the frontend HTTPS origin for `CORS_ORIGINS` and the backend HTTPS URL for `NEXT_PUBLIC_API_URL`. Credentials belong in service secrets, never in this repository. Creating this configuration does not mean the services have been deployed.

## Validation

```bash
cd backend
python -m pytest -q
cd ../frontend
npm ci
npm run build
```

The local suite verifies credit limits, payment allocations, reconciliation, close-day guards, maintenance, export formats/formula protection, price snapshots, session revocation, MFA recovery, rate limits and legacy migration/history preservation. Two posting-race tests require a dedicated PostgreSQL database and are skipped in the SQLite run.

```bash
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/fuelflow_test python -m pytest -q
```

PostgreSQL tests create and remove only their own randomly named test schemas. The database name must start with `fuelflow_test`. Do not point tests at a live database. GitHub Actions runs both SQLite and PostgreSQL suites plus the frontend build.

## Accounting and operational boundaries

- Business dates use Ghana's UTC date. Only the latest business day can be reopened. Close a prior open day before opening a newer day; corrections to older closed periods require a current-day adjustment.
- Shift stock is posted at reconciliation, so tank balances during open shifts remain estimates. Credit charges must be within the meter sales submitted for that shift.
- Fuel collections and customer debt repayments are separate measures. Adding debt repayments to revenue would double-count the original credit sale.
- Daily close records physical-versus-book stock differences for investigation. It does not silently replace book stock or label a variance as misconduct.
- Management margin uses the latest recorded delivery price as an **estimated** fuel-cost reference, with approved expenses allocated by revenue. It is not FIFO/weighted-average inventory valuation or a complete statutory profit statement. Missing costs remain blank.
- Credit reports show current account balances; the date range does not turn them into historical as-of balance sheets. Customer statements retain their transaction dates and running balances.
- v0.1 did not capture delivery dates or a stock ledger. Migrating an existing v0.1 database records current stock as a migration baseline and dates legacy deliveries to migration day; prior delivery timing/stock history cannot be reconstructed reliably.
- Ordinary workflows cannot erase finalized financial records. Erroneous credit charges need an explicit audited reversal module in a future increment; do not edit ledger rows directly.

## Remaining broader specification

The items requested for v0.2 are implemented. Further master-prompt work includes payment gateways, separate physical pump entities and multi-nozzle shifts, structured shift handovers, attachment storage, notification delivery, offline/PWA workflows, inventory cost layers and transaction reversal workflows. Forecasting and hardware integrations are future work.

See [security and operations guidance](docs/SECURITY.md) for recovery, secret rotation, backups and production review. Live hosting, PostgreSQL CI results and browser-based acceptance checks should be verified separately before using real station records.
