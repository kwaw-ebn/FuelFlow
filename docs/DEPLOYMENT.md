# Deploy FuelFlow Ghana

## Database

Create a dedicated Neon project named **FuelFlow Ghana**, preferably in Frankfurt to match the provided Render configuration. Keep this application's records separate from NutriTrack, HealthSignal and other projects. Use its SSL PostgreSQL connection string as the backend's `DATABASE_URL`. Do not send database passwords in repository files.

The database URL must use `postgresql://`, `postgres://` or `postgresql+psycopg://`; the application normalizes the first two to the Psycopg driver. Preserve `sslmode=require`. Both pooled and direct Neon endpoints can serve the API; use a direct endpoint for migration/administrative work if you configure separate migration execution.

## Render Blueprint

Open https://dashboard.render.com/blueprint/new?repo=https://github.com/kwaw-ebn/FuelFlow and select the confirmed destination workspace. The repository must be connected to Render. The Blueprint defines:

- `fuelflow-api`: Python, `backend`, Frankfurt, free plan; installs dependencies and runs migrations before starting Uvicorn.
- `fuelflow-web`: Node, `frontend`, Frankfurt, free plan; reproducible `npm ci` build and Next.js server.

Set these values:

| Service | Variable | Value |
| --- | --- | --- |
| API | DATABASE_URL | Dedicated Neon SSL connection URL |
| API | CORS_ORIGINS | Exact frontend HTTPS origin, with no trailing slash |
| Web | NEXT_PUBLIC_API_URL | Exact API HTTPS origin, with no trailing slash |

The Blueprint generates `JWT_SECRET`, `MFA_ENCRYPTION_SECRET` and `BOOTSTRAP_TOKEN`. Keep the MFA encryption secret stable; changing it without re-enrollment would make stored authenticator secrets unreadable. The API enables production-mode owner MFA and disables public interactive API documentation.

Service URLs are assigned by Render. Once both exist, update CORS and the frontend API URL to the **actual** assigned addresses, then rebuild the frontend so its public API URL and CSP use the correct origin. Never place database credentials or installation secrets in `NEXT_PUBLIC_*` variables.

## First owner

1. Verify API `/ready` responds with `{"status":"ready"}`.
2. Open the frontend. Its installation screen is shown only when no owner exists.
3. Retrieve `BOOTSTRAP_TOKEN` privately from the API environment settings and enter it as the installation access code.
4. Choose your own owner name, email and password of at least 12 characters.
5. Sign in. Add FuelFlow to an authenticator app using the displayed setup key and confirm a code.
6. Save the one-time recovery codes securely, then dismiss them from the screen.
7. Remove `BOOTSTRAP_TOKEN` from the API environment after completing installation. The endpoint also rejects installation once an owner exists.

You can instead create an owner through the interactive CLI with authorized database access. There is no public registration and no default password.

## Acceptance checks

Use a test station before importing real records:

1. Create products, a tank, nozzle and attendant; check capacity/stock.
2. Open a shift. Record a credit sale and a cash/MoMo/card sale total within meter sales.
3. Submit and reconcile; verify expected revenue, variance and stock.
4. Receive a partial customer payment; verify debt decreases and fuel revenue does not increase.
5. Record and approve an expense. Record a fresh tank dip and close the day.
6. Confirm late financial postings are blocked, and only the owner can reopen with a reason.
7. Open a maintenance job for linked nozzle equipment; verify new shifts are blocked until repair completion.
8. Download CSV, Excel and PDF reports. Check both desktop and phone layouts.
9. Sign out and confirm that the old session cannot access the API.

Monitor deployment logs and readiness after each migration. If a deployment fails, diagnose the actual logs before changing database regions or credentials. The service configuration is ready, but account-specific provisioning needs a confirmed Render workspace and a dedicated Neon project ID/connection.
