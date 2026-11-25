"""Validate implementation-plan links, checkpoint/finding coverage and frozen hashes.

No network, credentials or application database access. Run from any directory.
"""
from pathlib import Path
import csv
import hashlib
import json
import re
import sys
from urllib.parse import unquote

API = Path(__file__).resolve().parents[3]
PLAN = API / 'docs/ebrain/implementation-plan'
errors = []
markdown = sorted(PLAN.rglob('*.md')) + [API / 'tools/ebrain/README.md']
for doc in markdown:
    content = doc.read_text(encoding='utf-8')
    for target in re.findall(r'(?<!!)\[[^\]]+\]\(([^)]+)\)', content):
        target = target.strip('<>').split('#', 1)[0]
        if not target or re.match(r'^[a-zA-Z]+:', target):
            continue
        if not (doc.parent / unquote(target)).resolve().exists():
            errors.append(f'Broken link: {doc.relative_to(API)} -> {target}')

expected = {f'{prefix}{i:02}' for prefix in ('C', 'H', 'M') for i in range(1, 11)}
with (PLAN / 'TRACEABILITY.csv').open(encoding='utf-8', newline='') as f:
    findings = list(csv.DictReader(f))
if len(findings) != 30 or {row['finding_id'] for row in findings} != expected:
    errors.append('Expected exactly 30 unique C01-C10/H01-H10/M01-M10 findings')
for row in findings:
    if not (PLAN / row['milestone_readme']).is_file():
        errors.append('Missing primary milestone for ' + row['finding_id'])
    if not row['planned_test'] or not row['acceptance'] or row['status'] not in {'NOT_STARTED','IN_PROGRESS','PASS','FAIL','NOT_RUN'}:
        errors.append('Incomplete traceability row: ' + row['finding_id'])

with (PLAN / 'CHECKPOINTS.csv').open(encoding='utf-8', newline='') as f:
    checkpoints = list(csv.DictReader(f))
counts = {7:6,8:7,9:6,10:6,11:7,12:6,13:7,14:7}
expected_cp = {f'CP{m}.{n}' for m, count in counts.items() for n in range(1,count+1)}
if len(checkpoints) != len(expected_cp) or {r['checkpoint_id'] for r in checkpoints} != expected_cp:
    errors.append('Missing/duplicate milestone checkpoint IDs')
for row in checkpoints:
    path = PLAN / row['milestone_readme']
    if not path.is_file() or row['checkpoint_id'] not in path.read_text(encoding='utf-8'):
        errors.append('Checkpoint not specified in milestone: ' + row['checkpoint_id'])

manifest = json.loads((PLAN / 'evidence/relocation-manifest.json').read_text(encoding='utf-8'))
for row in manifest['retained']:
    path = API / row['new_path']
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
        errors.append('Frozen relocation changed/missing: ' + row['new_path'])
spec = API / manifest['spec_current']
if not spec.is_file() or hashlib.sha256(spec.read_bytes()).hexdigest() != manifest['spec_sha256']:
    errors.append('V3 spec differs from preserved owner source')
print(json.dumps({'markdown_files':len(markdown),'findings':len(findings),'checkpoints':len(checkpoints),'frozen_files':len(manifest['retained']),'errors':errors},indent=2))
sys.exit(bool(errors))
