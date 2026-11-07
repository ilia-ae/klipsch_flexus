# Testing

## Molecule (HACS-like install/upgrade on real HA)

The pytest suites (`tests/`) test the integration against Home Assistant's test harness. The
Molecule scenarios add what those cannot see: the integration installed into the **official Home
Assistant container image** the way HACS installs it, Home Assistant restarted, the soundbar added
through the real config flow, and the result checked through Home Assistant's own REST and
WebSocket APIs.

Everything here is test-only. The only hosts are throwaway `klipsch-flexus-*` containers on an
internal Docker network (no route to the internet or the LAN). The "soundbar" is a fake device
inside the same container. Nothing in this repository deploys to a real Home Assistant: users and
the owner install and update the integration through HACS.

### Run

From the repository root (GNU make 3.81 or newer, Docker, Python 3.13 at
`/opt/homebrew/bin/python3.13`, or set `ANSIBLE_PYTHON`):

```sh
make venv collections lint-ansible
make molecule-scenarios SCENARIOS="klipsch_flexus_install/fresh klipsch_flexus_install/upgrade klipsch_flexus_install/minimum"
make molecule-list                                           # every scenario
```

`make venv` creates `.venv` from `requirements-dev.txt` (pinned ansible-core, ansible-lint,
molecule, molecule-plugins[docker], yamllint). `make collections` installs the pinned collections
of `ansible/requirements.yml` into `ansible/collections`. Both directories are gitignored; in a git
worktree run both targets there (or symlink them from the main checkout, never commit the links).

`molecule-scenarios` runs one full `molecule test` per scenario (create, prepare, converge,
idempotence, verify, destroy), one at a time because the Docker VM is shared, and prints a summary.
It exits non-zero when any scenario failed. Each scenario takes about 2 to 3 minutes on an Apple
Silicon Mac.

Inner loop on a kept container:

```sh
make molecule-scenarios SCENARIOS=klipsch_flexus_install/fresh MOLECULE_ARGS=--destroy=never
make molecule-stage STAGE=converge S=klipsch_flexus_install/fresh   # also: create prepare idempotence verify destroy
make molecule-cleanup SCENARIOS=klipsch_flexus_install/fresh        # no SCENARIOS = every scenario
```

`molecule-cleanup` removes only the scenario's own `klipsch-flexus-*` container and network and
its `.molecule/<role>/<scenario>` state, never another container. If Docker Desktop restarts
under a run ("unexpected EOF", "docker.sock ... no such file"), that is infrastructure, not a test
result: `scripts/molecule.sh` waits until `docker info` answers and reruns that scenario once.

### Pieces

| Path | What it is |
|---|---|
| `ansible/roles/klipsch_flexus_install` | Installs `custom_components/klipsch_flexus` like HACS: a full replace of `/config/custom_components/klipsch_flexus` from a source tree on the controller (this checkout, or an older release from `git archive`), compared by content (files that Home Assistant compiles into `__pycache__` are ignored). Only when something changed it restarts Home Assistant through the image's s6 supervisor (`s6-svc -h`: SIGHUP is Home Assistant's "restart", exit code 100 keeps the container up) and waits until the new process answers. A second run reports `changed=0` and does not restart. |
| `ansible/roles/flexus_stub` | A fake Klipsch Flexus (Python stdlib) supervised by s6 next to Home Assistant, on loopback `127.0.0.2` (ports 80 and 8008). It serves `getData` (value and edit roles), `getRows` (`dirac:filters`), `setData` (POST, `authMode` `none`; the legacy GET answers 405 like 2026 firmware) and `eureka_info` from the non-secret `files/fixture.json` (MAC `02:00:00:00:00:01`, a locally administered documentation address; `eureka_info` reports the all-zero MAC as 2026 firmware does). Every write is recorded in `/var/lib/flexus-stub/writes.jsonl`; a read of a path the fixture does not know answers 404 and is recorded in `unknown_paths.jsonl`. |
| `ansible/molecule/resources` | Shared playbook tasks, variables and `ha_api.py`, a small REST/WebSocket client that runs inside the container with the image's Python: onboarding of a test owner (`/api/onboarding/users` -> auth code -> `/auth/token` -> long-lived token), REST and WebSocket calls, image hashes. |
| `scripts/molecule.sh`, `mk/ansible.mk` | The runner behind the make targets (sequential runs, summary, cleanup, Docker-restart rerun). |

Home Assistant images are pinned by their multi-arch index digest (linux/amd64 and linux/arm64);
Docker runs the host's architecture natively, so every scenario runs on an Apple Silicon Mac and
on amd64 CI runners alike.

### What each scenario proves

**`klipsch_flexus_install/fresh`** (Home Assistant 2026.10.4): a new HACS user.

- The role installs this checkout and restarts Home Assistant; the second run changes nothing and
  does not restart (idempotence).
- Home Assistant loaded the checkout's version (WebSocket `manifest/get`) and logged that it found
  the custom integration.
- The config flow's user step (host `127.0.0.2`) creates an entry titled from `eureka_info`
  that reaches state `loaded`, and its unique_id is the device's primary MAC (`020000000001`),
  not the host (read from `.storage/core.config_entries`: no API exposes a config entry's
  unique_id).
- Every expected entity exists (media player, the six selects including `6. Idle Timeout`, the
  thirteen numbers, the sensors and switches) and none is the old idle-timeout number. Their
  states come from the stub: media player `playing` at volume 0.4 (20 of the 0..50 range read
  from the `edit` metadata), source `TV ARC`, sound mode, title and artist; idle timeout
  `10_min` (600 s), EQ preset `custom`, Dirac filter `Living Room` (from `getRows`), tone and
  channel levels, balance, switches, the device-status sensor and a delay sensor.
- Setting up the integration wrote nothing to the device. `media_player.volume_set` 0.3 and
  `select.select_option` `15_min` reach the stub as exactly two writes (`player:volume` i32 15,
  `settings:/system/maxIdleTime` i32 900), and the entities show the values read back.
- The integration read no path the stub does not emulate.
- `GET /api/brands/integration/klipsch_flexus/{icon,icon@2x,dark_icon,dark_icon@2x}.png` answer 200
  with the exact bytes of `custom_components/klipsch_flexus/brand/` (Home Assistant 2026.3+
  serves an integration's own brand images before the CDN: the dark-theme logo fix).
- No `ERROR`/`CRITICAL` line mentioning `klipsch_flexus` and no traceback frame in
  `custom_components/klipsch_flexus/` in the container log (`docker logs`: every Home Assistant
  run of the container), no such error in Home Assistant's system log, and no warning at all from
  the integration's own loggers.

**`klipsch_flexus_install/upgrade`** (Home Assistant 2026.10.4): what a HACS user experiences on
update.

- prepare: release v2.5.17, extracted from this repository with `git archive v2.5.17` (no network;
  the tag must be in the clone), is installed with the same role and Home Assistant restarted; the
  soundbar is added through the config flow. Recorded in the container: the entry, its unique_id
  (v2.5.17 keys it by host because `eureka_info` reports the all-zero MAC), the entity registry
  (it has `number.*_idle_timeout`) and the number of writes so far.
- converge: this checkout replaces v2.5.17 like a HACS update, then a restart; idempotence as above.
- verify: the same entry is still the only one and `loaded`, now keyed by the stub's MAC; a second
  config flow for the same soundbar under another address (`127.0.0.3`) aborts with
  `already_configured`. The number idle timeout is gone from the registry and from the states, the
  select `6. Idle Timeout` exists with the stub's value, and every other entity kept its entity_id
  (dashboards and automations keep working). All entity states as in `fresh`, the update wrote
  nothing to the device, brand images byte for byte, and the logs of both releases are clean.

**`klipsch_flexus_install/minimum`** (Home Assistant 2024.11.0, the oldest supported release, as in
`.github/ci/requirements_test_min.txt`): fresh install and restart, config flow to `loaded` with
the MAC unique_id, the same entities, states and two writes as `fresh`, and clean logs. No
brand-image check: Home Assistant before 2026.3 has no local brands.
