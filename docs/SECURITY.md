# Security and operational notes

## Implemented controls

- Passwords use a unique random salt and scrypt; passwords are never returned through staff APIs.
- Bearer access tokens are held in browser memory. A database session record supports sign-out revocation, account disabling and password-change invalidation. Sessions expire after 15 minutes idle and 30 minutes total.
- Login permits six attempts per account and thirty per client IP per fixed minute. Counters live in the database and therefore cover multiple API workers. Authenticator enrollment/confirmation also has a per-account rate limit. Proxy-aware client addressing must be verified on the host.
- Production requires owner authenticator enrollment before access to station data. TOTP secrets are encrypted with the separate MFA encryption secret. Recovery codes are hashed, single-use and invalidate their use after redemption. TOTP timesteps cannot be reused.
- Authorization is checked on the server; staff are station-scoped and attendants can access only their assigned shift records. The owner controls all stations in this installation.
- PostgreSQL operations lock the station before changing financial, stock or day-close state. Nozzle shifts have a partial unique index; amounts and volumes have database checks; delivery/credit/payment references are unique.
- Audit/history and posted ledgers have database UPDATE/DELETE rejection triggers. These protect normal database operations; an administrator with DDL privileges can still alter/drop triggers. Do not describe this as tamper-proof against a database administrator.
- Financial records have no delete endpoints. Daily reopening, price changes, stock adjustments, access changes and password recovery produce audit entries.
- Exports neutralize spreadsheet formula prefixes. PDF text is escaped. HTTPS origins must be configured; the API uses no-store headers and the frontend includes a Content Security Policy and frame protections.

## Owner recovery

Prefer a saved authenticator recovery code. If both the authenticator and recovery codes are lost, a database administrator can run:

```bash
cd backend
python -m app.manage recover-owner --email OWNER_EMAIL
```

This prompts for a replacement password and a reason. It revokes existing sessions, clears old MFA enrollment and records an audit event. Production login then requires fresh enrollment. Never run this for another person's account without authorization.

Staff passwords can be reset by the owner under Staff. Staff disabling or reset revokes existing sessions. There is no email-based password reset service yet.

## Secrets and database roles

Store all credentials in hosting secrets. Keep `MFA_ENCRYPTION_SECRET` stable and backed up securely. Rotating `JWT_SECRET` revokes token signatures; MFA remains usable when a separate encryption secret is configured. Do not commit `.env` or upload production logs containing credentials.

Before real financial use, use a restricted application database role without schema/DDL privileges and a separate administrative role for migrations. Grant only needed reads/inserts/updates. Retain history triggers and deny direct modification of posted ledgers. The supplied startup migration uses the configured database account; splitting runtime and migration roles is an operational deployment step.

## Backups and release review

Use the database account's configured recovery features and maintain encrypted exports/backups appropriate for the business. Test restoring to an isolated database and confirm user, credit, close and stock records. Back up before upgrading an existing installation. Do not delete or reset a live branch to test a change.

Review GitHub Actions PostgreSQL results, deployed readiness/logs, actual CORS origins, authenticator recovery and desktop/mobile workflows before accepting live station data. The local SQLite tests do not validate PostgreSQL concurrency. Browser acceptance checks and hosted connectivity need a working deployment.

The system currently has no document uploads, online payment gateway credentials or card PAN/CVV/PIN fields. Adding these later requires a separately reviewed storage/payment design. Offline writes and notification channels are not implemented.
