#!/usr/bin/env bash
export PATH="/opt/itmo-j3312-k8s/bin:$PATH"
if [[ -z "${DOCKER_HOST:-}" && -S /run/itmo-j3312-docker/docker.sock ]]; then
    export DOCKER_HOST=unix:///run/itmo-j3312-docker/docker.sock
fi
export KUBECONFIG="${KUBECONFIG:-/var/lib/itmo-j3312-k8s/kubeconfig}"
export KIND_EXPERIMENTAL_PROVIDER=docker
