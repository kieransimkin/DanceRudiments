#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f tools/mesh_demo_assets/app.js ]]; then
  echo 'Run this script from the DanceRudiments repository root.' >&2
  exit 2
fi
branch="$(git branch --show-current)"
if [[ "$branch" == main ]]; then
  target=kandi-boom-final-integration
  if git show-ref --verify --quiet "refs/heads/$target"; then
    echo "Local branch $target already exists. Switch to it or remove/rename it before retrying." >&2
    exit 2
  fi
  git switch -c "$target"
fi
python3 "$(cd "$(dirname "$0")" && pwd)/apply_kandi_boom_final.py"
printf '\nIntegration applied. Suggested verification:\n'
printf '  npm ci\n  npm test\n'
printf '  python -m unittest discover -s tests/python -p "test_kandi_boom_*.py" -v\n'
printf '  python -m unittest discover -s tests/python -p test_mesh_demo_assets.py -v\n'
printf '  python -m unittest discover -s tests/python -p test_release_pages.py -v\n'
printf '  git diff --check\n  git status --short\n'
