#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/local-env.sh
export DOCKER_HOST=unix:///run/itmo-j3312-docker/docker.sock
tools=/opt/itmo-j3312-k8s/bin
install -d "$tools" /run/itmo-j3312-docker /var/lib/itmo-j3312-k8s
for tool in kind kubectl; do
    if ! test -x "$tools/$tool"; then
        expected=$(cut -d' ' -f1 "tmp/$tool.sha256")
        echo "$expected  tmp/$tool" | sha256sum -c -
        install -m755 "tmp/$tool" "$tools/$tool"
    fi
done
if ! test -x "$tools/dockerd"; then
    tar -xzf tmp/docker.tgz --strip-components=1 -C "$tools"
fi
if ! systemctl is-active --quiet itmo-j3312-docker.service; then
    systemd-run --unit=itmo-j3312-docker --property=Delegate=yes --setenv="PATH=$PATH" \
        "$tools/dockerd" --host="$DOCKER_HOST" --data-root=/var/lib/itmo-j3312-docker \
        --exec-root=/run/itmo-j3312-docker/exec --pidfile=/run/itmo-j3312-docker/docker.pid
fi
for i in {1..30}; do
    if docker info >/dev/null 2>&1; then break; fi
    sleep 1
done
docker version --format 'Docker client {{.Client.Version}}, server {{.Server.Version}}'
kind version
kubectl version --client
