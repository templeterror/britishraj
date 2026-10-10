#!/usr/bin/env bash
# Create gitignored env files from the templates. Never overwrites a file
# that is already present, so a teammate's filled-in secrets stay put.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"

copy_if_missing() {
  local src="$1"
  local dest="$2"
  if [[ -f "$dest" ]]; then
    echo "keep    ${dest#"$root"/}"
  else
    cp "$src" "$dest"
    echo "created ${dest#"$root"/}"
  fi
}

copy_if_missing "$root/frontend/.env.example" "$root/frontend/.env.local"
copy_if_missing "$root/backend/.env.example" "$root/backend/.env"

cat <<EOF

Next: paste the shared development keys into the two files above.
Both developers use the same Clerk development instance and the same Supabase project.
Then run ./scripts/check-env.sh
EOF
