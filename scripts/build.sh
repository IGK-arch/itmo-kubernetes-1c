#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/local-env.sh
DOCKER_BUILDKIT=0 docker build --network=none -t skills-1c:lab5 . 2>&1 | tee evidence/build.txt
docker image inspect skills-1c:lab5 --format '{{.Id}} {{.Os}}/{{.Architecture}}' | tee evidence/image-id.txt
