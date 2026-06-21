# Fixture overview

These fixtures encode the PRD/test-spec contract without assuming the final
Python module layout.

- `local_rime_base/` — local Rime dir with a valid local `.sync` workspace
- `incompatible_sync_dir/` — current repo migration edge: cloud-backed Nutstore
  `sync_dir`
- `missing_installation_yaml/` — fail-closed validation case
- `remote_all_devices/` — allowlisted multi-device `*.userdb.txt` snapshots
- `remote_polluted/` — remote noise that must never be merged or uploaded
