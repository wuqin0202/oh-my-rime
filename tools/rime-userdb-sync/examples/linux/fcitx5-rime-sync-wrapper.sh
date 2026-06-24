#!/usr/bin/env bash
set -euo pipefail

# Run the local Rime merge command without racing Fcitx5's LevelDB locks.
#
# Fcitx5 keeps *.userdb/LOCK open while it is running.  rime_dict_manager needs
# exclusive access when merging snapshots, so this wrapper briefly asks Fcitx5
# to exit, waits for the userdb locks to disappear, runs the merge, and starts
# Fcitx5 again if it was running before.

RIME_USER_DIR="${RIME_USER_DIR:-$HOME/.local/share/fcitx5/rime}"
LOCK_WAIT_SECONDS="${LOCK_WAIT_SECONDS:-10}"
FCITX5_RESTART_DELAY_SECONDS="${FCITX5_RESTART_DELAY_SECONDS:-1}"

was_running=0

fcitx5_process_is_running() {
  pgrep -x fcitx5 >/dev/null 2>&1
}

fcitx5_is_running() {
  fcitx5_process_is_running && return 0
  if command -v fcitx5-remote >/dev/null 2>&1; then
    fcitx5-remote --check >/dev/null 2>&1 && return 0
  fi
  return 1
}

locks_are_free() {
  if ! command -v lsof >/dev/null 2>&1; then
    # Without lsof, fall back to process-exit checks.  This is less precise but
    # avoids making lsof a hard dependency of the wrapper.
    ! pgrep -x fcitx5 >/dev/null 2>&1
    return
  fi

  local lock_files=()
  while IFS= read -r -d '' lock_file; do
    lock_files+=("$lock_file")
  done < <(find "$RIME_USER_DIR" -maxdepth 2 -type f -name LOCK -path '*.userdb/LOCK' -print0 2>/dev/null)

  if [ "${#lock_files[@]}" -eq 0 ]; then
    return 0
  fi

  ! lsof "${lock_files[@]}" >/dev/null 2>&1
}

wait_for_locks() {
  local deadline=$((SECONDS + LOCK_WAIT_SECONDS))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if locks_are_free; then
      return 0
    fi
    sleep 0.2
  done
  locks_are_free
}

stop_fcitx5_for_merge() {
  if ! fcitx5_is_running; then
    return 0
  fi

  was_running=1

  if command -v fcitx5-remote >/dev/null 2>&1; then
    fcitx5-remote -e >/dev/null 2>&1 || true
  fi

  if wait_for_locks; then
    return 0
  fi

  # Graceful D-Bus exit may fail if fcitx5 was started outside the current
  # session environment.  Use SIGTERM as a bounded fallback, then wait again.
  pkill -TERM -x fcitx5 >/dev/null 2>&1 || true
  if wait_for_locks; then
    return 0
  fi

  echo "timed out waiting for Fcitx5 to release Rime userdb locks under: $RIME_USER_DIR" >&2
  return 1
}

start_fcitx5_detached() {
  if command -v systemd-run >/dev/null 2>&1; then
    # A process started directly by this oneshot service remains in the service
    # cgroup and may be killed when the service exits.  Start Fcitx5 in a
    # separate transient user unit when systemd-run is available.
    systemctl --user reset-failed rime-userdb-sync-fcitx5.service >/dev/null 2>&1 || true
    systemd-run --user \
      --unit=rime-userdb-sync-fcitx5 \
      --collect \
      --description="Fcitx5 restarted after Rime UserDB sync" \
      /usr/bin/fcitx5 >/dev/null 2>&1 && return 0
  fi

  fcitx5 -d >/dev/null 2>&1 || true
}

restart_fcitx5_if_needed() {
  if [ "$was_running" -ne 1 ]; then
    return 0
  fi
  if fcitx5_process_is_running; then
    return 0
  fi
  sleep "$FCITX5_RESTART_DELAY_SECONDS"
  start_fcitx5_detached

  local deadline=$((SECONDS + 5))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if fcitx5_process_is_running; then
      return 0
    fi
    sleep 0.2
  done

  echo "warning: attempted to restart Fcitx5, but no fcitx5 process is running" >&2
}

trap restart_fcitx5_if_needed EXIT

run_merge_command() {
  local output_file
  output_file="$(mktemp -t rime-userdb-sync.XXXXXX)"
  local attempts="${RIME_MERGE_ATTEMPTS:-3}"
  local attempt=1
  local status=0

  while [ "$attempt" -le "$attempts" ]; do
    stop_fcitx5_for_merge

    if [ "$#" -gt 0 ]; then
      "$@" >"$output_file" 2>&1 && {
        rm -f "$output_file"
        return 0
      }
    else
      rime_dict_manager --sync >"$output_file" 2>&1 && {
        rm -f "$output_file"
        return 0
      }
    fi
    status=$?

    if ! grep -Eq 'LOCK|Resource temporarily unavailable|Error opening db' "$output_file"; then
      cat "$output_file" >&2
      rm -f "$output_file"
      return "$status"
    fi

    cat "$output_file" >&2
    if [ "$attempt" -lt "$attempts" ]; then
      echo "Rime userdb lock conflict during merge; retrying attempt $((attempt + 1))/$attempts" >&2
      sleep 1
    fi
    attempt=$((attempt + 1))
  done

  rm -f "$output_file"
  return "$status"
}

run_merge_command "$@"
