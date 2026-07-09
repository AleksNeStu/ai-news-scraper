# Hand-offs

Architectural hand-offs produced by `/agents` runs on this repo.

## Convention

File name: `YYYY-MM-DD-taskN-<slug>-<role>.md`

| Suffix | Producer | Read by | Notes |
|--------|----------|---------|-------|
| `-fetcher-contract.md` | Architect | Frontend | TS signature + URL contract + mount point |
| `-types-mirror.md` | Architect | Backend | TS ↔ Pydantic schema alignment |
| `-role-handoff.md` | Architect | anyone | Generic cross-layer contract |

## Lifecycle

- Written by Architect during Wave 1 of a `/agents` run
- Read by the implementation teammates in subsequent waves
- Committed to the repo at the end of the run as part of PM synthesis
- Cross-referenced from the implementation commit bodies (e.g. "Per Architect hand-off at docs/handoffs/...")
- Reviewed by Devil for scope cleanliness

## Why committed (not gitignored)

The hand-off doc is referenced by name in implementation commit bodies.
Keeping it tracked makes the cross-team contract discoverable to future readers
without needing to clone a side-channel workspace.

## When to update or remove

- Update: when a new `/agents` run supersedes a prior contract (new file; old file stays for history)
- Remove: when the underlying feature is removed or renamed
