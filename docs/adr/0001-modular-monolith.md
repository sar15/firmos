# ADR 0001: Modular monolith

Status: accepted — 14 July 2026

## Decision

Keep one repository with the Next.js web app, FastAPI backend, Supabase migrations and Tally desktop agent. Separate responsibility through backend modules and narrow HTTP boundaries, not premature services.

## Consequences

- Shared database transactions, audit records and connector policies stay simple.
- Routes remain thin; connector SDK calls and domain logic do not accumulate in them.
- A service split needs evidence of an independent deployment, scaling or fault-isolation requirement.
