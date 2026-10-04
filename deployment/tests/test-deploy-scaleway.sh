#!/usr/bin/env bash
# Behaviour tests for deploy-scaleway.sh, run with mocked docker/git so no
# container, network or repository is touched. Wired into CI (ci.yml,
# deploy-scripts job); runnable directly: bash deployment/tests/test-deploy-scaleway.sh
#
# What is locked here (each rule exists because its absence was a review
# finding on the per-service deploy PR):
#   - A pin is written to services/.deployed-refs only after the deploy has
#     succeeded. A failed `compose up` must leave the previous pins in place.
#   - A resolved ref that differs from the recorded pin forces --build, so the
#     image always matches the checkout the pin will describe.
#   - A targeted deploy re-pins only its own service and never reloads nginx.
#   - --service nginx touches no pins at all (nginx is not a pinned checkout).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/../deploy-scaleway.sh"

pass=0; fail=0
check() { # check <description> <expected> <actual>
  if [[ "$2" == "$3" ]]; then
    echo "ok   - $1"; pass=$((pass+1))
  else
    echo "FAIL - $1"
    echo "      expected [$2]"
    echo "      got      [$3]"
    fail=$((fail+1))
  fi
}

# sandbox <seed-pin-file(0|1)> <ENCODER_REF> <extra-args...>
# Prints "rc=<n> pin=<ref-or-(none)> build=<yes|no> reload=<yes|no>".
# UP_FAIL=1 in the environment makes the mocked `docker compose up` fail.
sandbox() {
  local seed="$1"; shift
  local encoder_ref="$1"; shift
  local tmp; tmp=$(mktemp -d "${TMPDIR:-/tmp}/lux-deploy-test.XXXXXX")
  mkdir -p "$tmp/bin" "$tmp/deployment/nginx" "$tmp/deployment/services/server_encoder/.git"

  # Mock docker: logs every call, serves `config --services`, fails `up` when
  # UP_FAIL=1. Logging goes through $MOCK_LOG because the mock runs as a child
  # process and cannot see this function's locals.
  cat > "$tmp/bin/docker" <<'MOCK'
#!/usr/bin/env bash
echo "docker $*" >> "$MOCK_LOG"
saw_config=false
for a in "$@"; do
  [ "$a" = "config" ] && saw_config=true
  if [ "$a" = "up" ] && [ "$MOCK_UP_FAIL" = "1" ]; then
    echo "mock compose up failed" >&2
    exit 1
  fi
done
if [ "$saw_config" = true ]; then
  printf 'nginx\nserver-lux\nredis\nencoder-service\nmerger-service\nstats-service\nautoheal\n'
fi
exit 0
MOCK
  cat > "$tmp/bin/git" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK
  chmod +x "$tmp/bin/docker" "$tmp/bin/git"

  if [[ "$seed" == 1 ]]; then
    printf 'encoder=v1.0.0\nmerger=master\nstats=master\n' > "$tmp/deployment/services/.deployed-refs"
  fi
  printf 'MODEL_SERVICE_URL=https://mock--upskiller.modal.run\nAUTH_TYPE=none\nMODAL_KEY=k\nMODAL_SECRET=s\nENCODER_REF=%s\n' \
    "$encoder_ref" > "$tmp/deployment/.env.scaleway"
  cp "$DEPLOY_SCRIPT" "$tmp/deployment/"
  printf '# stub compose file (docker is mocked)\n' > "$tmp/deployment/docker-compose.scaleway.yml"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/deployment/nginx/update-cloudflare-ips.sh"

  local rc=0
  MOCK_LOG="$tmp/docker.log" MOCK_UP_FAIL="${UP_FAIL:-0}" \
    PATH="$tmp/bin:$PATH" bash "$tmp/deployment/deploy-scaleway.sh" "$@" \
    > "$tmp/out.log" 2>&1 || rc=$?

  local pin="(none)"
  [[ -f "$tmp/deployment/services/.deployed-refs" ]] \
    && pin=$(sed -n 's/^encoder=//p' "$tmp/deployment/services/.deployed-refs" | tail -n 1)
  local built=no reloaded=no
  [[ -f "$tmp/docker.log" ]] && grep -q " up .*--build" "$tmp/docker.log" && built=yes
  grep -q "nginx -s reload" "$tmp/docker.log" 2>/dev/null && reloaded=yes
  echo "rc=$rc pin=$pin build=$built reload=$reloaded"
  rm -rf "$tmp"
}

# ── Pin timing ────────────────────────────────────────────────────────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0)
check "unchanged ref full stack: success, pin kept, no build forced, gateway reloaded" \
  "rc=0 pin=v1.0.0 build=no reload=yes" "$out"

out=$(sandbox 1 v1.2.0)
check "changed ref full stack: build forced, pin updated" \
  "rc=0 pin=v1.2.0 build=yes reload=yes" "$out"

UP_FAIL=1
out=$(sandbox 1 v1.2.0)
check "failed deploy: previous pin kept, no reload past the failure" \
  "rc=1 pin=v1.0.0 build=yes reload=no" "$out"

out=$(sandbox 0 v1.2.0)
check "failed deploy on a fresh box: no pin file at all" \
  "rc=1 pin=(none) build=yes reload=no" "$out"

# ── Targeted deploys ─────────────────────────────────────────────────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0 --service encoder-service)
check "targeted unchanged ref: no build, pin rewritten, gateway untouched" \
  "rc=0 pin=v1.0.0 build=no reload=no" "$out"

out=$(sandbox 1 v2.0.0 --service encoder-service)
check "targeted changed ref: build forced, pin updated, gateway untouched" \
  "rc=0 pin=v2.0.0 build=yes reload=no" "$out"

UP_FAIL=1
out=$(sandbox 1 v2.0.0 --service encoder-service)
check "targeted failed deploy: previous pin kept" \
  "rc=1 pin=v1.0.0 build=yes reload=no" "$out"

# ── --service nginx: no checkout, so no pins and no forced build ───────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0 --service nginx)
check "targeted nginx deploy: pins untouched, gateway reloaded" \
  "rc=0 pin=v1.0.0 build=no reload=yes" "$out"

echo
echo "PASS=$pass FAIL=$fail"
[[ $fail -eq 0 ]]