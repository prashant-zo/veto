#!/usr/bin/env bash
# prints where the project is, from real files and git, not memory
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "## state.md"
cat docs/state.md
echo
echo "## git"
echo "branch: $(git branch --show-current)"
git --no-pager log --oneline -10
echo
echo "uncommitted:"
git status --short
echo
echo "## files"
git ls-files | grep -v '\.gitkeep$'
echo
echo "## tools"
for c in "python3 --version" "uv --version" "kind version" "kubectl version --client" "helm version --short" "gitleaks version"; do
  printf '%s: ' "${c%% *}"; eval "$c" 2>&1 | head -1
done
echo
echo "## cluster"
colima list 2>/dev/null | tail -n +2
kind get clusters 2>/dev/null
kubectl --context kind-veto get nodes --request-timeout=3s 2>/dev/null || echo "kind-veto not reachable"
