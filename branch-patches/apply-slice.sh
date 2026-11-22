#!/bin/bash
# Apply one slice patch to the current git working tree (run from the repo root).
#   ../branch-patches/apply-slice.sh 02-crud
# Uses `patch`, not git. Afterwards review the files, then commit them yourself.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
patch -p1 --forward --no-backup-if-mismatch < "$here/$1.patch"
# diff/patch do not carry the executable bit; the pipeline runs these directly.
[ -d scripts ] && chmod +x scripts/*.sh
echo "Applied $1. Now: review, git add -A, git commit."
