#!/usr/bin/env bash
# Behaviour tests for deploy-scaleway.sh, run with mocked docker/git so no
# container, network or repository is touched. Wired into CI (ci.yml,
# deploy-scripts job); runnable directly: bash deployment/tests/test-deploy-scaleway.sh
#
# What is locked here (each rule exists because its absence was a review
# finding on the per-service deploy PR):
#   - A pin is written to services/.deployed-refs only after the deploy has
#     succeeded. A failed `compose up` must leave the previous pins in place.
#   - A checkout whose COMMIT differs from the recorded one forces --build, so
#     the image always matches the checkout the pin will describe. Comparing ref
#     names instead would miss a moved `master` or a force-moved tag: same name,
#     new code, no rebuild — the running image silently stale.
#   - A superseded release is refused. GitHub does not guarantee the execution
#     order of runs in a concurrency group, so two tags pushed together can
#     reach the box newest-first; an older <NAME>_ORDER must not roll the
#     service back over the newer one already deployed.
#   - A targeted deploy re-pins only its own service and never reloads nginx.
#   - --service nginx touches no pins at all (nginx is not a pinned checkout).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_SCRIPT="$SCRIPT_DIR/../deploy-scaleway.sh"

pass=0; fail=0
# The commit a checkout lands on unless a test overrides COMMIT/SEED_COMMIT.
DEFAULT_COMMIT="c0ffee0000000000000000000000000000000001"
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
# Environment knobs:
#   UP_FAIL=1     makes the mocked `docker compose up` fail.
#   COMMIT=<sha>  the commit the checkout lands on this run (what `git rev-parse
#                 HEAD` reports).
#   SEED_COMMIT=<sha>  the commit the seeded pin file records. Equal to COMMIT
#                 means "the checkout did not move"; different means new code
#                 regardless of whether the ref NAME changed.
#   SEED_REF=<ref>  the ref the seeded pin file records (default v1.0.0). Set it
#                 equal to the deployed ref to hold the NAME constant while only
#                 the commit moves — the case a name comparison cannot see.
#   ORDER=<n>       ENCODER_ORDER for this run (the sender's release counter).
#   SEED_ORDER=<n>  the order the seeded pin file records as already deployed.
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
  # Mock git: fetch/clone/checkout are no-ops, but `rev-parse HEAD` must report
  # a commit, since that is what the rebuild decision compares.
  cat > "$tmp/bin/git" <<'MOCK'
#!/usr/bin/env bash
for a in "$@"; do
  if [ "$a" = "rev-parse" ]; then
    echo "$MOCK_COMMIT"
    exit 0
  fi
done
exit 0
MOCK
  chmod +x "$tmp/bin/docker" "$tmp/bin/git"

  if [[ "$seed" == 1 ]]; then
    {
      printf 'encoder=%s\nmerger=master\nstats=master\n' "${SEED_REF:-v1.0.0}"
      printf 'encoder.commit=%s\nmerger.commit=%s\nstats.commit=%s\n' \
        "${SEED_COMMIT:-$DEFAULT_COMMIT}" "${SEED_COMMIT:-$DEFAULT_COMMIT}" "${SEED_COMMIT:-$DEFAULT_COMMIT}"
      [ -n "${SEED_ORDER:-}" ] && printf 'encoder.order=%s\n' "$SEED_ORDER"
    } > "$tmp/deployment/services/.deployed-refs"
  fi
  printf 'MODEL_SERVICE_URL=https://mock--upskiller.modal.run\nAUTH_TYPE=none\nMODAL_KEY=k\nMODAL_SECRET=s\nENCODER_REF=%s\n' \
    "$encoder_ref" > "$tmp/deployment/.env.scaleway"
  [ -n "${ORDER:-}" ] && printf 'ENCODER_ORDER=%s\n' "$ORDER" >> "$tmp/deployment/.env.scaleway"
  cp "$DEPLOY_SCRIPT" "$tmp/deployment/"
  printf '# stub compose file (docker is mocked)\n' > "$tmp/deployment/docker-compose.scaleway.yml"
  printf '#!/usr/bin/env bash\nexit 0\n' > "$tmp/deployment/nginx/update-cloudflare-ips.sh"

  local rc=0
  MOCK_LOG="$tmp/docker.log" MOCK_UP_FAIL="${UP_FAIL:-0}" \
    MOCK_COMMIT="${COMMIT:-$DEFAULT_COMMIT}" \
    PATH="$tmp/bin:$PATH" bash "$tmp/deployment/deploy-scaleway.sh" "$@" \
    > "$tmp/out.log" 2>&1 || rc=$?

  local pin="(none)"
  [[ -f "$tmp/deployment/services/.deployed-refs" ]] \
    && pin=$(sed -n 's/^encoder=//p' "$tmp/deployment/services/.deployed-refs" | tail -n 1)
  local recorded_order="(none)"
  [[ -f "$tmp/deployment/services/.deployed-refs" ]] \
    && recorded_order=$(sed -n 's/^encoder\.order=//p' "$tmp/deployment/services/.deployed-refs" | tail -n 1)
  [[ -z "$recorded_order" ]] && recorded_order="(none)"
  local built=no reloaded=no
  [[ -f "$tmp/docker.log" ]] && grep -q " up .*--build" "$tmp/docker.log" && built=yes
  grep -q "nginx -s reload" "$tmp/docker.log" 2>/dev/null && reloaded=yes
  echo "rc=$rc pin=$pin order=$recorded_order build=$built reload=$reloaded"
  rm -rf "$tmp"
}

NEW_COMMIT="f00d000000000000000000000000000000000002"

# ── Pin timing ────────────────────────────────────────────────────────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0)
check "unchanged ref full stack: success, pin kept, no build forced, gateway reloaded" \
  "rc=0 pin=v1.0.0 order=(none) build=no reload=yes" "$out"

COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v1.2.0)
check "changed ref full stack: build forced, pin updated" \
  "rc=0 pin=v1.2.0 order=(none) build=yes reload=yes" "$out"

UP_FAIL=1
out=$(sandbox 1 v1.2.0)
check "failed deploy: previous pin kept, no reload past the failure" \
  "rc=1 pin=v1.0.0 order=(none) build=yes reload=no" "$out"
unset COMMIT

out=$(sandbox 0 v1.2.0)
check "failed deploy on a fresh box: no pin file at all" \
  "rc=1 pin=(none) order=(none) build=yes reload=no" "$out"

# ── A ref name that stays put while the code moves ───────────────────────────
# `master` is mutable and a tag can be force-pushed, so an unchanged ref NAME
# says nothing about whether the checkout moved. Comparing names would skip the
# rebuild here and leave the old image running under a pin claiming otherwise.
UP_FAIL=0
# SEED_REF == the deployed ref, so the NAME is identical on both sides and only
# the commit differs. A name comparison sees "unchanged" and skips the rebuild.
SEED_REF=master
SEED_COMMIT="$DEFAULT_COMMIT"
COMMIT="$NEW_COMMIT"
out=$(sandbox 1 master)
check "same ref name, moved commit: build forced" \
  "rc=0 pin=master order=(none) build=yes reload=yes" "$out"

SEED_REF=v1.0.0
out=$(sandbox 1 v1.0.0 --service encoder-service)
check "same ref name, moved commit, targeted: build forced" \
  "rc=0 pin=v1.0.0 order=(none) build=yes reload=no" "$out"
unset COMMIT SEED_COMMIT SEED_REF

# A retagged commit is the converse: new name, identical code, nothing to build.
SEED_COMMIT="$DEFAULT_COMMIT"
out=$(sandbox 1 v9.9.9)
check "new ref name, same commit: no build forced" \
  "rc=0 pin=v9.9.9 order=(none) build=no reload=yes" "$out"
unset SEED_COMMIT

# ── Targeted deploys ─────────────────────────────────────────────────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0 --service encoder-service)
check "targeted unchanged ref: no build, pin rewritten, gateway untouched" \
  "rc=0 pin=v1.0.0 order=(none) build=no reload=no" "$out"

COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v2.0.0 --service encoder-service)
check "targeted changed ref: build forced, pin updated, gateway untouched" \
  "rc=0 pin=v2.0.0 order=(none) build=yes reload=no" "$out"

UP_FAIL=1
out=$(sandbox 1 v2.0.0 --service encoder-service)
check "targeted failed deploy: previous pin kept" \
  "rc=1 pin=v1.0.0 order=(none) build=yes reload=no" "$out"
unset COMMIT

# ── Release order: a superseded tag must not roll the service back ───────────
# GitHub does not guarantee the execution order of runs in a concurrency group,
# so two tags pushed together can arrive here newest-first. The deploy, not the
# workflow, is where that has to be caught — by then the runs are serialised and
# this one holds the lock.
UP_FAIL=0
SEED_ORDER=200
ORDER=100
COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v0.9.0 --service encoder-service)
check "older release targeted: refused, pin and order untouched, nothing built" \
  "rc=0 pin=v1.0.0 order=200 build=no reload=no" "$out"
unset ORDER SEED_ORDER COMMIT

SEED_ORDER=100
ORDER=200
COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v2.0.0 --service encoder-service)
check "newer release targeted: deployed, pin and order advanced" \
  "rc=0 pin=v2.0.0 order=200 build=yes reload=no" "$out"
unset ORDER SEED_ORDER COMMIT

# Re-running the same release is a retry, not a rollback — it must be allowed.
SEED_ORDER=200
ORDER=200
COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v2.0.0 --service encoder-service)
check "same release re-run: allowed" \
  "rc=0 pin=v2.0.0 order=200 build=yes reload=no" "$out"
unset ORDER SEED_ORDER COMMIT

# A manual deploy carries no order. It must not be blocked by one on record,
# or a human could never intervene after a tag deploy.
SEED_ORDER=200
COMMIT="$NEW_COMMIT"
out=$(sandbox 1 v3.0.0 --service encoder-service)
check "manual deploy with no order: not blocked, order left as recorded" \
  "rc=0 pin=v3.0.0 order=200 build=yes reload=no" "$out"
unset SEED_ORDER COMMIT

# ── --service nginx: no checkout, so no pins and no forced build ───────────────
UP_FAIL=0
out=$(sandbox 1 v1.0.0 --service nginx)
check "targeted nginx deploy: pins untouched, gateway reloaded" \
  "rc=0 pin=v1.0.0 order=(none) build=no reload=yes" "$out"

echo
echo "PASS=$pass FAIL=$fail"
[[ $fail -eq 0 ]]