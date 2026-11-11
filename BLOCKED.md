# Blocked items

Nothing is blocked. Going public and publishing are left to the owner on purpose; see `RELEASE.md`.

## Resolved

- **2026-11-12: unpushed commits, CI on the final commit, and history with private details (former items 1–3).** The build session's push was refused three times, and older commits held private details that were removed later (`docs/verification/audits.md`). The parent session built one parentless commit from the verified-clean tree and gated it with the owner's out-of-repo privacy checks (private-terms scan of every object, binary strings, identities, gitleaks). It created a fresh private `vulbsti/agent-readback` with only `main` and `v0.1.0`. The old repository was deleted on 2026-11-12. Commit SHAs cited from before that date belonged to the deleted pre-release repository.
