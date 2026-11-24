#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/local-env.sh
mkdir -p tmp "$(dirname "$KUBECONFIG")"
test -r "${CSV:=$PWD/../lab3-mapreduce/data/it_vacancies_2024.csv}"
export CSV
python3 - <<'PY'
import json, os, pathlib
config = {
    "kind": "Cluster", "apiVersion": "kind.x-k8s.io/v1alpha4",
    "networking": {"apiServerAddress": "127.0.0.1"},
    "nodes": [{"role": "control-plane", "extraMounts": [{
        "hostPath": str(pathlib.Path(os.environ["CSV"]).resolve()),
        "containerPath": "/lab-input/it_vacancies_2024.csv", "readOnly": True}]}]}
pathlib.Path("tmp/kind.json").write_text(json.dumps(config, ensure_ascii=False))
PY
if ! kind get clusters | grep -Fxq itmo-j3312; then
    kind create cluster --name itmo-j3312 --config tmp/kind.json --kubeconfig "$KUBECONFIG" \
         --image kindest/node:v1.34.0@sha256:7416a61b42b1662ca6ca89f02028ac133a309a2a30ba309614e8ec94d976dc5a --wait 180s
elif [[ "$(docker inspect --format '{{.State.Running}}' itmo-j3312-control-plane)" != true ]]; then
    docker start itmo-j3312-control-plane
fi
for i in {1..60}; do kubectl get --raw=/readyz --request-timeout=2s >/dev/null 2>&1 && break; sleep 2; done
kubectl wait --for=condition=Ready node --all --timeout=180s
kubectl get nodes -o wide
kubectl get pods -A -o wide
