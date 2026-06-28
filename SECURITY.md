# Security Policy

## Reporting a vulnerability

**Do not file public GitHub issues for security bugs.**

Email: **a.v.nesterovich@gmail.com**
Subject prefix: `[SECURITY]`

Please include:
- Description of the vulnerability
- Reproduction steps
- Affected version / commit
- Potential impact

## Response timeline

| Severity | Acknowledgment | Target fix |
|---|---|---|
| P0 (critical — RCE, auth bypass) | within 24h | within 7 days |
| P1 (high — data exposure, privilege escalation) | within 72h | within 30 days |
| P2 (medium — DoS, info leak) | within 7 days | within 90 days |
| P3 (low — best-practice deviation) | best effort | best effort |

## Supported versions

| Version | Supported |
|---|---|
| `dev` (active development) | ✅ |
| `main` (latest release) | ✅ |
| Older | ❌ |

## Security features (current)

- **JWT auth** — httpOnly cookies, HS256, bcrypt-hashed passwords.
- **Input validation** — Pydantic schemas on every endpoint.
- **Rate limiting** — planned (P1 in roadmap).
- **Dependency scanning** — Dependabot security-only updates weekly.
- **Secret hygiene** — `.env` gitignored; `.env.example` is the only tracked env file.
- **No GPL/AGPL** — license policy enforced at PR review.

## Best practices for contributors

- Never commit secrets (API keys, tokens, passwords). Use `.env`.
- Never log user passwords or tokens, even hashed.
- Use parameterized queries (SQLAlchemy ORM does this by default).
- Validate inputs via Pydantic schemas — do not trust raw request bodies.
- Report vulnerabilities privately — do not disclose publicly before a fix is released.

See [`docs/PROJECT_RULES.md`](docs/PROJECT_RULES.md) for the full set of hard rules.
