#!/usr/bin/env bash
# Capture only this private X display. Each file is input to an actual bash in xterm.
set -euo pipefail
cd "$(dirname "$0")/.."
source scripts/local-env.sh
export TERM=xterm-256color
cap=/var/lib/itmo-j3312-k8s/capture
export LD_LIBRARY_PATH="$cap/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export DISPLAY=:93
mkdir -p tmp/terminal evidence/screenshots
"$cap/usr/bin/Xvfb" "$DISPLAY" -screen 0 1500x750x24 -nolisten tcp -noreset >tmp/terminal/xvfb.log 2>&1 &
xpid=$!
trap 'kill "$xpid" 2>/dev/null || true' EXIT
for i in {1..30}; do xdpyinfo >/dev/null 2>&1 && break; sleep .2; done
capture() {
    local name=$1 cols=$2 rows=$3
    if [[ "${target:-all}" != all && "$target" != "$name" ]]; then
        cat >/dev/null
        return
    fi
    rm -f -- "tmp/terminal/$name.done"
    cat > "tmp/terminal/$name.cmd"
    "$cap/usr/bin/xterm" -title "$name" -fa "DejaVu Sans Mono" -fs 12 -geometry "${cols}x${rows}+0+0" \
        -bg '#18212c' -fg '#f2f5f7' -b 12 -xrm 'XTerm.vt100.cursorBlink:false' -e bash scripts/show-terminal.sh "$name" &
    local tpid=$!
    for i in {1..100}; do test -f "tmp/terminal/$name.done" && break; sleep .2; done
    test -f "tmp/terminal/$name.done"
    sleep .4
    xwd -name "$name" -silent -out "tmp/terminal/$name.xwd"
    kill "$tpid" 2>/dev/null || true
    wait "$tpid" 2>/dev/null || true
}
target=${1:-all}
capture memory 84 12 <<'CMDS'
kubectl get nodes
kubectl -n skills-1c get pods | grep -E 'NAME|pairs-(oom|profile|tuned)'
kubectl -n skills-1c describe pod -l job-name=pairs-oom | grep 'Exit Code'
CMDS
capture storage 82 13 <<'CMDS'
kubectl -n skills-1c get pvc | awk '{print $1,$2,$4}' | column -t
kubectl -n skills-1c get jobs pairs-index pairs-map pairs-reduce
CMDS
reference=../lab3-mapreduce/results/optimized-1/skills_2.csv
[[ -f "$reference" ]] || reference=reference/skills_2.csv
capture result 90 7 <<CMDS
wc -c results/skills_2.csv
sha256sum results/skills_2.csv
cmp results/skills_2.csv $reference && echo OK
CMDS
waiter=$(python3 -c "import json; print(json.load(open('evidence/scheduling.json'))['waiter'])")
export WAIT_POD="$waiter"
capture cpu 86 11 <<'CMDS'
kubectl -n skills-1c events --for="pod/$WAIT_POD" --types=Warning
awk '/^cpu-wait/{print $1,$3}' evidence/cpu-simultaneous.txt
awk '/^cpu-wait/{print $1,$3}' evidence/cpu-after-release.txt
CMDS
if [[ "$target" == all || "$target" == scheduler ]]; then
    kubectl create -f manifests/quota-first.json
    kubectl -n skills-quota wait --for=condition=Ready pod/quota-first --timeout=60s
fi
capture scheduler 87 12 <<'CMDS'
kubectl -n skills-1c get events --field-selector reason=Preempted
kubectl -n skills-quota create -f manifests/quota-second.json
CMDS
if [[ "$target" == all || "$target" == scheduler ]]; then
    kubectl -n skills-quota delete pod quota-first --wait=true
fi
