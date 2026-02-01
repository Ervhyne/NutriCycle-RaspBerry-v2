#!/usr/bin/env bash
set -euo pipefail

# This script untracks model files from git (keeps them locally) and commits the change.
# Run from repo root: ./deploy/remove_tracked_models.sh

echo "This will remove tracked model files from git index (they will remain in your working tree)."
read -p "Proceed? [y/N] " ans
if [[ "$ans" != "y" && "$ans" != "Y" ]]; then
  echo "Aborted."
  exit 1
fi

# Patterns to untrack
patterns=(
  "AI-Model/**/weights/*"
  "deploy/models/*"
  "*.pt"
  "*.onnx"
)

# Attempt to run git commands
if ! command -v git >/dev/null 2>&1; then
  echo "Error: git not found in PATH. Install Git and run this script again." >&2
  exit 2
fi

for p in "${patterns[@]}"; do
  echo "Removing tracked files matching: $p"
  git ls-files -- "$p" | xargs -r git rm --cached || true
done

# Commit the changes
git add .gitignore
git commit -m "chore: remove tracked model binaries; add .gitignore entries" || true

echo "Done. If you intend to track models via Git LFS, run:"
echo "  git lfs install"
echo "  git lfs track \"*.pt\" \"*.onnx\""
echo "  git add .gitattributes"
echo "and re-add/push models via LFS as needed."
