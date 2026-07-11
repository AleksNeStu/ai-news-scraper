# Open-Redirect Prevention — `next` Query Param

**Task:** #67
**Date:** 2026-07-11
**Owner:** Web (apps/web)

## Purpose

Acceptance-criteria checklist for `validateNextTarget()`. Maps every known
attack vector to a unit test name + expected helper output. Use as the
regression spec.

## Threat Model

OWASP Unvalidated Redirects cheatsheet framing. `next` is set by middleware
on the unauthenticated-user redirect. Today's login page hardcodes `/`, so
no consumer is currently vulnerable. We validate at the SET point so any
future consumer (loginAction, share-link, dashboard deep-link) can trust the
value as a same-origin relative path.

## Attack Vector Matrix

(Generated from `apps/web/src/lib/routing-helpers.test.ts → describe('validateNextTarget')`.
See that file for inputs + expected outputs.

| Attack vector | Input example | Expected output |
|---|---|---|
| Protocol-relative | `//evil.com/phish` | `/` |
| Backslash protocol-relative | `/\\evil.com/phish` | `/` |
| Double-backslash | `\\\\evil.com/phish` | `/` |
| Absolute http URL | `http://evil.com/phish` | `/` |
| Absolute https URL | `https://evil.com/phish` | `/` |
| Scheme injection | `javascript:alert(1)` | `/` |
| Missing leading slash | `evil.com/phish` | `/` |
| Relative traversal | `/../../admin` | `/../../admin` |
| Locale-prefixed path | `/en/dashboard` | `/en/dashboard` |
| Bare locale | `/en` | `/en` |
| Root | `/` | `/` |
| Empty / nullish / non-string | `''`, `null`, `undefined`, `42` | `/` |

## Regression Usage

Re-validate by running `pnpm test routing-helpers` and confirming every row
above has a matching test that passes.

## References

- ADR (local-only): `.agent/adr/021-open-redirect-prevention.md`
- Devil's post-commit finding on Task #66 (commit `017a97a`)
- OWASP Unvalidated Redirects cheatsheet: https://cheatsheetseries.owasp.org/cheatsheets/Unvalidated_Redirects_and_Forwards_Cheat_Sheet.html
