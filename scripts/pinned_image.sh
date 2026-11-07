#!/usr/bin/env bash
# Print the image reference to run for an official, digest-pinned image.
#
#   scripts/pinned_image.sh <official@sha256:...> <git-url#revision> <dockerfile> <local-name>
#
# hassfest and the HACS action publish linux/amd64 images only. Where this
# Docker engine runs amd64 natively, the official image is used, pinned by
# digest. Elsewhere (Apple Silicon without amd64 emulation in Docker Desktop:
# "exec format error") the same Dockerfile is built, once, at the upstream
# revision the official image was built from (its build provenance), for the
# native architecture, as <local-name>:<revision>.
#
# IMAGES=official|local overrides the automatic choice. Build output goes to
# stderr; stdout carries only the image reference.
set -euo pipefail

if [ "$#" -ne 4 ]; then
  echo "usage: $0 <official-image@digest> <git-url#revision> <dockerfile> <local-name>" >&2
  exit 2
fi
official=$1
source=$2
dockerfile=$3
name=$4
revision=${source##*#}
if ! [[ "$revision" =~ ^[0-9a-f]{40}$ ]]; then
  echo "$0: the source must be pinned to a full commit: $source" >&2
  exit 2
fi

mode=${IMAGES:-auto}
if [ "$mode" = auto ]; then
  case "$(docker info --format '{{.Architecture}}')" in
    x86_64 | amd64) mode=official ;;
    *) mode=local ;;
  esac
fi

case "$mode" in
  official)
    echo "$official"
    ;;
  local)
    tag="$name:$revision"
    if ! docker image inspect "$tag" > /dev/null 2>&1; then
      repo=${source%#*}
      repo=${repo%.git}
      case "$repo" in
        https://github.com/*/*) ;;
        *)
          echo "$0: only https://github.com/<owner>/<repo> sources are supported: $source" >&2
          exit 2
          ;;
      esac
      # GitHub's source archive of the pinned commit: far smaller than a clone.
      context=$(mktemp -d "${TMPDIR:-/tmp}/klipsch-flexus-image.XXXXXX")
      trap 'rm -rf "$context"' EXIT
      echo "building $tag from $source ($dockerfile), the source of $official" >&2
      curl -fsSL "https://codeload.github.com/${repo#https://github.com/}/tar.gz/$revision" |
        tar -xzf - -C "$context" --strip-components=1
      docker build --quiet --tag "$tag" --file "$context/$dockerfile" \
        --label "org.opencontainers.image.source=$source" \
        --label "org.opencontainers.image.base.name=$official" \
        "$context" >&2
    fi
    echo "$tag"
    ;;
  *)
    echo "$0: IMAGES must be auto, official or local, not '$mode'" >&2
    exit 2
    ;;
esac
