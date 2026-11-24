"""Download the pinned universal wheels with the SHA-256 published by PyPI."""
import hashlib
import json
import subprocess
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parents[1]
out = root / 'vendor'
out.mkdir(exist_ok=True)
for line in (root / 'requirements.txt').read_text().splitlines():
    name, version = line.split('==')
    url = f'https://pypi.org/pypi/{name}/{version}/json'
    with urllib.request.urlopen(url, timeout=40) as response:
        files = json.load(response)['urls']
    obj = next(f for f in files if f['filename'].endswith('none-any.whl'))
    target = out / obj['filename']
    if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest() != obj['digests']['sha256']:
        subprocess.run(['curl', '-fLsS', '--retry', '5', '--retry-all-errors', '--max-time', '180',
                        '-o', str(target), obj['url']], check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest() == obj['digests']['sha256']
    print(target.name, flush=True)
