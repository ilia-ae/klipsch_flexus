#!/usr/bin/env bash
# Runs the Molecule scenarios of the HACS-like harness one at a time and prints a summary
# (docs/TESTING.md, "Molecule"). Test-only: every scenario runs in throwaway klipsch-flexus-*
# containers; nothing here touches a real Home Assistant.
#
# The Docker VM is shared with other projects and agents, so scenarios never run in parallel. A
# failed scenario does not stop the run: every requested scenario runs, and the exit status is 1
# when any failed.
#
# Usage: scripts/molecule.sh [--list] [--cleanup] [--stage STAGE] [TARGET...]
#   TARGET     <role>/<scenario> (e.g. klipsch_flexus_install/fresh) or <role> (all its scenarios);
#              no TARGET = every scenario (--list and --cleanup only)
#   --list     print the matching scenarios, one per line, and exit. Needs no Docker.
#   --cleanup  after an interrupted run: remove the selected scenarios' containers and networks
#              (only names starting with "klipsch-flexus-"; never anything else) and their
#              .molecule/<role>/<scenario> state. Runs no Molecule stage.
#   --stage S  inner dev loop on a KEPT container instead of the full `molecule test`:
#              create | prepare | converge | idempotence | verify | destroy (one molecule
#              subcommand; only destroy removes the container). Default: the full test.
# Each scenario runs `molecule test` (create -> prepare -> converge -> idempotence -> verify ->
# destroy) with MOLECULE_EPHEMERAL_DIRECTORY=<repo>/.molecule/<role>/<scenario> (gitignored).
# When Docker Desktop restarts under a run ("unexpected EOF", "docker.sock ... no such file"),
# that is infrastructure, not a test result: the script waits until `docker info` answers and
# reruns that scenario once.
# Environment: MOLECULE (default: molecule from PATH; the Makefile puts .venv first),
#              MOLECULE_ARGS (extra `molecule test` arguments, word-split), DOCKER (default: docker).
#
# Written for bash 3.2 (macOS /bin/bash) as well as bash 5.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly ROLES_DIR="$repo_root/ansible/roles"
readonly STATE_ROOT="$repo_root/.molecule"
readonly PREFIX="klipsch-flexus-"
docker_bin="${DOCKER:-docker}"

# Molecule's Docker driver (the Python Docker SDK) only reads DOCKER_HOST or
# /var/run/docker.sock, while the docker CLI follows the active context. Docker Desktop
# does not always keep that /var/run symlink (and local CI scrubs DOCKER_HOST), so point
# the SDK at the active context's socket.
if [ -z "${DOCKER_HOST:-}" ] && [ ! -S /var/run/docker.sock ]; then
    DOCKER_HOST="$("$docker_bin" context inspect --format '{{.Endpoints.docker.Host}}' 2>/dev/null || true)"
    if [ -n "$DOCKER_HOST" ]; then
        export DOCKER_HOST
    else
        unset DOCKER_HOST
    fi
fi

usage() {
    awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "${BASH_SOURCE[0]}"
}

list_only=0
cleanup=0
stage="test"
targets=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --list) list_only=1 ;;
        --cleanup) cleanup=1 ;;
        --stage)
            if [[ $# -lt 2 ]]; then
                echo "--stage needs a value" >&2
                exit 2
            fi
            stage="$2"
            shift
            ;;
        -h | --help)
            usage
            exit 0
            ;;
        -*)
            echo "unknown option: $1" >&2
            exit 2
            ;;
        *) targets+=("$1") ;;
    esac
    shift
done

case "$stage" in
    test | create | prepare | converge | idempotence | verify | destroy) ;;
    *)
        echo "unknown stage: $stage (create|prepare|converge|idempotence|verify|destroy)" >&2
        exit 2
        ;;
esac

# A directory is a scenario only when it holds a molecule.yml (molecule/resources is not one).
discover_role() {
    local f
    for f in "$ROLES_DIR/$1"/molecule/*/molecule.yml; do
        [[ -f "$f" ]] || continue
        f="${f%/molecule.yml}"
        echo "$1/${f##*/}"
    done
}

discover_all() {
    local d
    for d in "$ROLES_DIR"/*/; do
        d="${d%/}"
        discover_role "${d##*/}"
    done
}

expand_target() {
    local target="$1" found
    case "$target" in
        */*) found="$(discover_role "${target%%/*}" | grep -Fx -- "$target" || true)" ;;
        *) found="$(discover_role "$target")" ;;
    esac
    if [[ -z "$found" ]]; then
        echo "no Molecule scenario matches: $target (make molecule-list)" >&2
        return 2
    fi
    echo "$found"
}

selected=()
if [[ ${#targets[@]} -eq 0 ]]; then
    if [[ $list_only -eq 0 && $cleanup -eq 0 ]]; then
        usage >&2
        exit 2
    fi
    targets=(all)
fi
for target in "${targets[@]}"; do
    if [[ "$target" == "all" ]]; then
        expanded="$(discover_all)"
    else
        expanded="$(expand_target "$target")" || exit 2
    fi
    while IFS= read -r item; do
        [[ -n "$item" ]] || continue
        dup=0
        for seen in ${selected[@]+"${selected[@]}"}; do
            [[ "$seen" == "$item" ]] && dup=1
        done
        [[ $dup -eq 1 ]] || selected+=("$item")
    done <<<"$expanded"
done

if [[ $list_only -eq 1 ]]; then
    [[ ${#selected[@]} -eq 0 ]] || printf '%s\n' "${selected[@]}"
    exit 0
fi

scenario_file() { echo "$ROLES_DIR/${1%%/*}/molecule/${1#*/}/molecule.yml"; }
state_dir() { echo "$STATE_ROOT/${1%%/*}/${1#*/}"; }

# Container and network names of a scenario: the "- name:" entries under platforms: (the
# platforms themselves and their docker_networks / networks). A line-based parse of the house
# molecule.yml layout; only names with the prefix are ever acted on.
scenario_names() {
    awk '
        /^platforms:/ { inside = 1; next }
        inside && /^[^[:space:]#]/ { inside = 0 }
        inside && /^[[:space:]]*-[[:space:]]+name:[[:space:]]*/ {
            sub(/^[[:space:]]*-[[:space:]]+name:[[:space:]]*/, "")
            sub(/[[:space:]]+#.*$/, "")
            gsub(/["'\'']/, "")
            print
        }' "$(scenario_file "$1")" | sort -u
}

docker_ready() { "$docker_bin" info >/dev/null 2>&1; }

wait_for_docker() {
    local i
    for i in $(seq 1 60); do
        docker_ready && return 0
        echo "=== waiting for Docker (docker info does not answer yet, $i/60)"
        sleep 5
    done
    return 1
}

cleanup_scenario() {
    local item="$1" name rc=0
    while IFS= read -r name; do
        [[ -n "$name" ]] || continue
        if [[ "$name" != "$PREFIX"* ]]; then
            echo "=== cleanup $item: refusing '$name' (not $PREFIX*)" >&2
            rc=1
            continue
        fi
        # Exact names only (docker's name filter is a regex: anchor it).
        if [[ -n "$("$docker_bin" ps -aq --filter "name=^/${name}\$")" ]]; then
            echo "=== cleanup $item: docker rm -f $name"
            "$docker_bin" rm -f "$name" >/dev/null || rc=1
        fi
        if [[ -n "$("$docker_bin" network ls -q --filter "name=^${name}\$")" ]]; then
            echo "=== cleanup $item: docker network rm $name"
            "$docker_bin" network rm "$name" >/dev/null || rc=1
        fi
    done < <(scenario_names "$item")
    rm -rf "$(state_dir "$item")"
    return $rc
}

if [[ $cleanup -eq 1 ]]; then
    if ! docker_ready; then
        echo "docker info failed: Docker is not answering; wait until it does, then rerun" >&2
        exit 2
    fi
    rc=0
    for item in "${selected[@]}"; do
        cleanup_scenario "$item" || rc=1
    done
    exit $rc
fi

molecule_bin="${MOLECULE:-molecule}"
if ! command -v "$molecule_bin" >/dev/null 2>&1; then
    echo "molecule not found ($molecule_bin): run 'make venv' or set MOLECULE" >&2
    exit 2
fi
molecule_args=()
if [[ -n "${MOLECULE_ARGS:-}" ]]; then
    read -r -a molecule_args <<<"$MOLECULE_ARGS"
fi

for item in "${selected[@]}"; do
    while IFS= read -r name; do
        if [[ -n "$name" && "$name" != "$PREFIX"* ]]; then
            echo "$item: platform/network name '$name' must start with '$PREFIX' (shared Docker daemon)" >&2
            exit 2
        fi
    done < <(scenario_names "$item")
done

run_scenario() { # <item> <log file>
    local item="$1" log="$2" dir state
    dir="$ROLES_DIR/${item%%/*}"
    state="$(state_dir "$item")"
    mkdir -p "$state"
    local extra=()
    if [[ "$stage" == "test" ]]; then
        extra=(${molecule_args[@]+"${molecule_args[@]}"})
    fi
    echo "=== molecule $item: cd ${dir#"$repo_root"/} && molecule $stage -s ${item#*/}${extra[*]:+ ${extra[*]}}"
    (cd "$dir" && MOLECULE_EPHEMERAL_DIRECTORY="$state" \
        "$molecule_bin" "$stage" -s "${item#*/}" ${extra[@]+"${extra[@]}"}) 2>&1 | tee "$log"
}

infra_failure() { # <log file>: Docker Desktop went away under the run
    grep -Eq 'unexpected EOF|docker\.sock.*(no such file|connection refused)|Cannot connect to the Docker daemon' "$1" || ! docker_ready
}

results=()
failed=0
log_dir="$(mktemp -d "${TMPDIR:-/tmp}/klipsch-flexus-molecule.XXXXXX")"
for item in "${selected[@]}"; do
    start=$SECONDS
    log="$log_dir/${item//\//_}.log"
    status="PASS"
    note=""
    if ! run_scenario "$item" "$log"; then
        status="FAIL"
        if [[ "$stage" == "test" ]] && infra_failure "$log"; then
            echo "=== molecule $item: Docker went away during the run (infrastructure, not a test result)"
            if wait_for_docker; then
                cleanup_scenario "$item" || true
                note=", rerun after a Docker restart"
                if run_scenario "$item" "$log"; then
                    status="PASS"
                fi
            fi
        fi
    fi
    [[ "$status" == "PASS" ]] || failed=$((failed + 1))
    elapsed=$((SECONDS - start))
    echo "=== molecule $item: $status ($stage) in $((elapsed / 60))m$((elapsed % 60))s$note"
    results+=("$status  $item  ($stage, $((elapsed / 60))m$((elapsed % 60))s$note)")
done
rm -rf "$log_dir"

echo
echo "Molecule summary:"
printf '  %s\n' "${results[@]}"
if [[ $failed -gt 0 ]]; then
    echo "$failed scenario(s) failed" >&2
    exit 1
fi
