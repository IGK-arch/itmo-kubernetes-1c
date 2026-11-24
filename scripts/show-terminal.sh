#!/usr/bin/env bash
set -euo pipefail
source scripts/local-env.sh
name=$1
while IFS= read -r command; do
    printf '\033[1;36m$\033[0m %s\n' "$command"
    if ! bash -c "$command"; then
        [[ "$name" == scheduler && "$command" == 'kubectl -n skills-quota create -f manifests/quota-second.json' ]] || exit 1
    fi
done < "tmp/terminal/$name.cmd"
touch "tmp/terminal/$name.done"
sleep 45
