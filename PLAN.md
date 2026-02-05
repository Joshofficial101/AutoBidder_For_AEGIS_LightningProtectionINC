# SaaS Migration Plan (AWS + Python)

## Goals
- Host the app on AWS as a web-based SaaS.
- Keep backend logic in Python with SQL database.
- Replace the current desktop UI with a web frontend (no Flutter).

## Recommended Stack
- Frontend: Next.js (React)
- Backend: FastAPI (Python)
- Database: PostgreSQL (AWS RDS)
- File Storage: S3
- CDN: CloudFront
- Auth: Cognito (or Auth0)
- Background Jobs: SQS + Worker (for PDF/Excel parsing)
- Logging/Monitoring: CloudWatch

## Why This Stack
- Next.js is the most common SaaS frontend and has the strongest ecosystem.
- FastAPI is Python-native, fast, and plays well with async/background tasks.
- PostgreSQL is SaaS-standard and scalable.
- AWS services are durable and easy to expand as you sell to more users.

## Phased Roadmap

### Phase 1 — Web-Ready Backend
1. Extract core business logic into a clean service layer.
2. Add REST API endpoints via FastAPI.
3. Swap SQLite for PostgreSQL.
4. Add authentication and user scoping (single-tenant first).

### Phase 2 — Web App
1. Build the Next.js UI (dashboard, bids, jobs, calendar).
2. Wire up API calls for all workflows.
3. Add file uploads (S3) and parsing pipeline.
4. Add role-based access (admin vs user).

### Phase 3 — SaaS Readiness
1. Multi-tenant support (organization/account model).
2. Billing + plans (Stripe).
3. Audit logs, usage metrics, and notifications.
4. Performance hardening and security review.

## Immediate Next Steps (This Week)
1. Decide frontend framework (Next.js recommended).
2. Decide initial hosting path (AWS ECS Fargate or Elastic Beanstalk).
3. Spin up a dev PostgreSQL instance locally or in RDS.
4. Sketch API endpoints from current GUI workflows.

## Open Questions
- Do you want the new UI to resemble the current desktop layout?
- Should we support multiple organizations from day one or add later?
- Do you want local/offline mode or fully cloud-only?

## Notes
- The current Flet GUI can remain as a local version while the web app is built.
- We can migrate incrementally to reduce risk and keep functionality working.
