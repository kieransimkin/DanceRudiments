#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f tools/mesh_demo_assets/app.js ]]; then
  echo 'Run this script from the DanceRudiments repository root.' >&2
  exit 2
fi
bundle_dir="$(cd "$(dirname "$0")" && pwd)"
for relative in \
  payload/tools/mesh_demo_assets/kandi-boom.js \
  payload/docs/mesh-demos.md \
  payload/docs/kandi-boom-integration.md \
  payload/tests/typescript/kandi-boom.test.js; do
  if [[ ! -f "$bundle_dir/$relative" ]]; then
    echo "Integration bundle is incomplete: missing $relative" >&2
    exit 2
  fi
done
branch="$(git branch --show-current)"
if [[ "$branch" == main ]]; then
  target=kandi-boom-final-integration
  if git show-ref --verify --quiet "refs/heads/$target"; then
    git switch "$target"
    echo "Switched to existing branch $target"
  else
    git switch -c "$target"
    echo "Created branch $target"
  fi
elif [[ "$branch" != kandi-boom-final-integration ]]; then
  echo "Applying on current branch '$branch' (not creating another branch)."
fi
python3 "$bundle_dir/apply_kandi_boom_final.py"
printf '\nIntegration applied. Suggested verification:\n'
printf '  npm ci\n  npm test\n'
printf '  python -m unittest discover -s tests/python -p "test_kandi_boom_*.py" -v\n'
printf '  python -m unittest discover -s tests/python -p test_mesh_demo_assets.py -v\n'
printf '  python -m unittest discover -s tests/python -p test_release_pages.py -v\n'
printf '  git diff --check\n  git status --short\n'
