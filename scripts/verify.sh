#!/usr/bin/env bash
# Re-run every mechanical release check and print a compact report.
# usage: scripts/verify.sh            (needs uv, docker for gitleaks, claude CLI for plugin validate)
set -uo pipefail
cd "$(dirname "$0")/.."
ok=0; fail=0
step() { printf '\n== %s\n' "$1"; }
check() { if "$@"; then echo "PASS"; ok=$((ok+1)); else echo "FAIL"; fail=$((fail+1)); fi; }

step "tests (uv run pytest -q)"
check bash -o pipefail -c 'uv run --quiet pytest -q 2>&1 | tail -1'

step "lint (ruff check + ruff format --check)"
check bash -o pipefail -c 'uv run --quiet ruff check . && uv run --quiet ruff format --check . | tail -1'

step "zero runtime dependencies"
check bash -o pipefail -c 'grep -n "^dependencies = \[\]" pyproject.toml'

step "eval transcripts sanitized"
check bash -o pipefail -c 'python3 eval/scripts/sanitize.py --check eval/sessions | tail -1 | grep -q " 0 finding" && echo "0 findings"'

# Privacy patterns: generic ones live here; patterns naming a specific person, machine or private tool
# live in an untracked file (default .work/private-patterns.txt, override READBACK_PRIVATE_PATTERNS).
PRIV=${READBACK_PRIVATE_PATTERNS:-.work/private-patterns.txt}
GENERIC='/home/(?!user\b)[a-z][a-z0-9_-]*/|[A-Za-z0-9._%+-]+@(?!example\.com|users\.noreply\.github\.com)(?!pytest\.)[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,6}\b|sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}'
if [ -f "$PRIV" ]; then PRIVPAT=$(grep -v -e '^#' -e '^rewrite:' -e '^$' "$PRIV" | paste -sd'|'); echo "(private pattern file: $(grep -vc '^#' "$PRIV") patterns)"; else PRIVPAT=""; echo "(no private pattern file at $PRIV: generic checks only)"; fi
export GENERIC PRIVPAT

step "privacy grep on tracked files (generic + private patterns)"
check bash -o pipefail -c '
hits=$(git ls-files -z | xargs -0 grep -I -n -P "$GENERIC" 2>/dev/null || true)
if [ -n "$PRIVPAT" ]; then hits="$hits$(git ls-files -z | xargs -0 grep -I -n -i -E "$PRIVPAT" 2>/dev/null || true)"; fi
if [ -n "$hits" ]; then echo "$hits" | cut -c1-160 | head; exit 1; else echo "0 hits in $(git ls-files | wc -l) tracked files"; fi'

step "privacy grep over git history (HEAD must be clean; earlier commits reported)"
check bash -o pipefail -c '
hit() { git grep -q -I -P "$GENERIC" "$1" -- . 2>/dev/null || { [ -n "$PRIVPAT" ] && git grep -q -I -i -E "$PRIVPAT" "$1" -- . 2>/dev/null; }; }
n=0; old=0
for c in $(git rev-list --all); do n=$((n+1)); hit "$c" && old=$((old+1)); done
echo "$n commits scanned; $old contain patterns removed later (published history must be rebuilt from HEAD: RELEASE.md step 1)"
! hit HEAD'

step "commit identities: only GitHub noreply addresses; no Co-Authored-By lines"
check bash -o pipefail -c '
git log --all --format="%ae%n%ce" | sort -u
! git log --all --format="%ae%n%ce" | grep -v -q -E "(users\.noreply\.github\.com|^noreply@github\.com)$" && ! git log --all --format=%B | grep -q -i "co-authored-by"'

step "gitleaks (full history)"
if command -v docker >/dev/null; then
  check bash -o pipefail -c 'docker run --rm -v "$PWD:/r" zricethezav/gitleaks git /r 2>&1 | tail -2 | grep -E "commits scanned|no leaks found" ; docker run --rm -v "$PWD:/r" zricethezav/gitleaks git /r >/dev/null 2>&1'
else echo "SKIP (no docker)"; fi

step "README media: each image < 2 MB, total < 10 MB"
check bash -o pipefail -c '
total=0; bad=0
for f in docs/img/*; do s=$(stat -c %s "$f"); total=$((total+s)); printf "%8d  %s\n" "$s" "$f"; [ "$s" -lt 2097152 ] || bad=1; done
echo "total $total bytes"; [ $bad = 0 ] && [ $total -lt 10485760 ]'

step "required project files"
check bash -o pipefail -c '
missing=0
for f in LICENSE README.md CONTRIBUTING.md CODE_OF_CONDUCT.md SECURITY.md CHANGELOG.md AGENTS.md DECISIONS.md \
  .github/CODEOWNERS .github/dependabot.yml .github/pull_request_template.md .github/workflows/ci.yml \
  .github/ISSUE_TEMPLATE/bug_report.yml .github/ISSUE_TEMPLATE/feature_request.yml \
  docs/architecture.md docs/usage.md docs/plugin.md docs/backends.md docs/ROADMAP.md docs/eval.md docs/alternatives.md \
  .claude-plugin/plugin.json .claude-plugin/marketplace.json commands/readback.md skills/readback/SKILL.md; do
  [ -s "$f" ] || { echo "missing $f"; missing=1; }; done
grep -q "Apache License" LICENSE && grep -q "Contributor Covenant" CODE_OF_CONDUCT.md && grep -q "@vulbsti" .github/CODEOWNERS
n=$(sed -n "/^## Good first issues/,/^## /p" docs/ROADMAP.md | grep -c "^### "); echo "ROADMAP good first issues: $n"; [ "$n" -ge 5 ] || missing=1
[ $missing = 0 ]'

step "Claude Code plugin manifest"
if command -v claude >/dev/null; then check bash -o pipefail -c 'claude plugin validate . 2>&1 | grep -E "Validation passed"'; else echo "SKIP (no claude CLI)"; fi

printf '\n== summary: %d passed, %d failed\n' "$ok" "$fail"
[ "$fail" = 0 ]
