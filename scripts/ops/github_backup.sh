#!/usr/bin/env bash
# YORVYN Safe GitHub Backup & Verification Workflow
# Never force-pushes, resets history, deletes remote branches, or commits secrets.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

BRANCH="${1:-$(git rev-parse --abbrev-ref HEAD)}"
COMMIT_MSG="${2:-}"
SKIP_TESTS="${SKIP_TESTS:-0}"

echo "=== [1/8] Inspecting Git status & branch ($BRANCH) ==="
git status --short

echo "=== [2/8] Checking for forbidden / large / unignored files ==="
FORBIDDEN_FILES="$(git status --porcelain | awk '{print $2}' | grep -E '(\.env$|\.env\.|dump\.rdb$|backend\.sock$|\.pt$|\.pth$|\.safetensors$|generated_3d/|wardrobe_assets/|temp_processing/)' || true)"
if [[ -n "$FORBIDDEN_FILES" ]]; then
  echo "ERROR: Forbidden or large runtime files detected in working tree:" >&2
  echo "$FORBIDDEN_FILES" >&2
  exit 1
fi

echo "=== [3/8] Scanning tracked & staged diffs for secrets ==="
SECRET_REGEX='(ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|sk_live_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{35}|-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----)'
if git diff HEAD | grep -E "$SECRET_REGEX" >/dev/null 2>&1; then
  echo "ERROR: Potential secret detected in git diff! Aborting backup." >&2
  exit 1
fi

echo "=== [4/8] Verifying .gitignore rules ==="
for pattern in ".env" "models/generated_3d/" "models/checkpoints/*.pt" "dump.rdb" "backend.sock"; do
  if ! grep -Fxq "$pattern" .gitignore; then
    echo "ERROR: Required ignore pattern '$pattern' missing from .gitignore" >&2
    exit 1
  fi
done

if [[ "$SKIP_TESTS" != "1" ]]; then
  echo "=== [5/8] Running verification checks ==="
  (cd frontend && npm test && npm run build)
else
  echo "=== [5/8] Skipping tests (SKIP_TESTS=1) ==="
fi

echo "=== [6/8] Commit check ==="
if [[ -n "$(git status --porcelain)" ]]; then
  if [[ -z "$COMMIT_MSG" ]]; then
    echo "Working tree has uncommitted changes, and no commit message was supplied."
    echo "Review changes with 'git status' / 'git diff', then re-run:"
    echo "  $0 \"$BRANCH\" \"feat(scope): concise description\""
    exit 2
  fi
  git add -A
  git commit -m "$COMMIT_MSG"
else
  echo "Working tree clean — nothing new to commit."
fi

LOCAL_SHA="$(git rev-parse HEAD)"
echo "Local HEAD SHA: $LOCAL_SHA"

echo "=== [7/8] Pushing safely to origin/$BRANCH (no force push) ==="
git push origin "$BRANCH"

echo "=== [8/8] Verifying remote commit SHA ==="
REMOTE_SHA="$(git ls-remote origin "refs/heads/$BRANCH" | awk '{print $1}')"
if [[ -z "$REMOTE_SHA" ]]; then
  echo "ERROR: Could not read remote ref refs/heads/$BRANCH" >&2
  exit 1
fi
if [[ "$LOCAL_SHA" != "$REMOTE_SHA" ]]; then
  echo "ERROR: Remote SHA ($REMOTE_SHA) != Local SHA ($LOCAL_SHA)" >&2
  exit 1
fi
echo "SUCCESS: origin/$BRANCH verified at $REMOTE_SHA"
