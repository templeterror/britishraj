#!/usr/bin/env bash
# Fail when a required local env value is missing, still a placeholder,
# a production Clerk key, or a Supabase secret leaked into the frontend.
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
frontend="$root/frontend/.env.local"
backend="$root/backend/.env"
fail=0

note() {
  echo "$1" >&2
  fail=1
}

# Last assignment wins. Ignores comments and blank lines. Strips matching quotes.
value_of() {
  local file="$1"
  local key="$2"
  local line val
  line="$(grep -E "^${key}=" "$file" 2>/dev/null | tail -n 1 || true)"
  val="${line#*=}"
  if [[ "$val" == \"*\" && "$val" == *\" ]]; then
    val="${val:1:${#val}-2}"
  elif [[ "$val" == \'*\' && "$val" == *\' ]]; then
    val="${val:1:${#val}-2}"
  fi
  printf '%s' "$val"
}

require_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    note "missing ${file#"$root"/} — run ./scripts/setup-env.sh"
    return 1
  fi
}

# Sets the named variable in the current shell. A command substitution would
# hide the failure flag, so callers pass the destination variable name.
require_value() {
  local file="$1"
  local key="$2"
  local dest="$3"
  local val
  val="$(value_of "$file" "$key")"
  printf -v "$dest" '%s' "$val"
  if [[ -z "$val" || "$val" == *REPLACE_ME* ]]; then
    note "unset   $key  (${file#"$root"/})"
  fi
}

require_file "$frontend" || true
require_file "$backend" || true

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

require_value "$frontend" NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY fe_pk
require_value "$frontend" CLERK_SECRET_KEY fe_sk
require_value "$frontend" NEXT_PUBLIC_SUPABASE_URL fe_url
require_value "$frontend" NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY fe_pub

require_value "$backend" CLERK_PUBLISHABLE_KEY be_pk
require_value "$backend" CLERK_SECRET_KEY be_sk
require_value "$backend" CLERK_DOMAIN be_domain
require_value "$backend" SUPABASE_URL be_url
require_value "$backend" SUPABASE_PUBLISHABLE_KEY be_pub
require_value "$backend" SUPABASE_SECRET_KEY be_secret
require_value "$backend" FRONTEND_ORIGIN be_origin

# XAI_API_KEY, AGENT_INTAKE_MODEL, AGENT_ANALYST_MODEL, and AGENT_ADVISOR_MODEL
# are optional. converse and analyze need the key; an empty value must not fail this check.

if grep -E '^(SUPABASE_SECRET_KEY|SUPABASE_SERVICE_ROLE_KEY)=' "$frontend" >/dev/null; then
  note "frontend/.env.local must not contain the Supabase secret key"
fi

if grep -E 'sb_secret_|service_role' "$frontend" >/dev/null; then
  note "frontend/.env.local contains a Supabase secret (sb_secret_ or service_role)"
fi

check_prefix() {
  local label="$1"
  local val="$2"
  local prefix="$3"
  if [[ "$val" == pk_live_* || "$val" == sk_live_* ]]; then
    note "$label is a production Clerk key"
  elif [[ -n "$val" && "$val" != *REPLACE_ME* && "$val" != "$prefix"* ]]; then
    note "$label must start with $prefix (development keys only)"
  fi
}

check_prefix "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY" "$fe_pk" "pk_test_"
check_prefix "frontend CLERK_SECRET_KEY" "$fe_sk" "sk_test_"
check_prefix "CLERK_PUBLISHABLE_KEY" "$be_pk" "pk_test_"
check_prefix "backend CLERK_SECRET_KEY" "$be_sk" "sk_test_"

same() {
  local label="$1"
  local a="$2"
  local b="$3"
  if [[ -n "$a" && -n "$b" && "$a" != *REPLACE_ME* && "$b" != *REPLACE_ME* && "$a" != "$b" ]]; then
    note "$label does not match between frontend/.env.local and backend/.env"
  fi
}

same "Clerk publishable key" "$fe_pk" "$be_pk"
same "Clerk secret key" "$fe_sk" "$be_sk"
same "Supabase URL" "$fe_url" "$be_url"
same "Supabase publishable key" "$fe_pub" "$be_pub"

if [[ -n "$fe_url" && "$fe_url" != *REPLACE_ME* && "$fe_url" == */rest/v1* ]]; then
  note "NEXT_PUBLIC_SUPABASE_URL should be the project origin, without /rest/v1"
fi
if [[ -n "$be_url" && "$be_url" != *REPLACE_ME* && "$be_url" == */rest/v1* ]]; then
  note "SUPABASE_URL should be the project origin, without /rest/v1"
fi
if [[ -n "$be_domain" && "$be_domain" != *REPLACE_ME* && "$be_domain" == http* ]]; then
  note "CLERK_DOMAIN should be the host only, without https://"
fi
if [[ -n "$be_secret" && -n "$be_pub" && "$be_secret" != *REPLACE_ME* && "$be_pub" != *REPLACE_ME* && "$be_secret" == "$be_pub" ]]; then
  note "SUPABASE_SECRET_KEY and SUPABASE_PUBLISHABLE_KEY must be different"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "env ok"
