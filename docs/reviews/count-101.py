#!/usr/bin/env python3
"""Report whitespace-word counts; never infer runtime tokens or behavior."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

BASE = 'bceb00a6d4a95f612cac4d6c7477beb45136f5b9'
p = argparse.ArgumentParser()
p.add_argument('root', type=Path)
p.add_argument('--candidate', help='commit/tree to count; default is working files')
a = p.parse_args()
def git(*args):
    return subprocess.check_output(['git', '-C', str(a.root), *args])
def names(ref):
    return git('ls-tree', '-r', '--name-only', ref).decode().splitlines()
def corpus(path):
    return path == 'AGENTS.md' or path.startswith('skills/') and path.endswith('.md')
def read(path, ref=None):
    return git('show', ref + ':' + path) if ref else (a.root / path).read_bytes()
def entry(path, content):
    return {'path': path, 'words': len(content.decode().split()),
            'sha256': hashlib.sha256(content).hexdigest()}
original = [entry(path, read(path, BASE)) for path in names(BASE) if corpus(path)]
current_paths = (names(a.candidate) if a.candidate else
                 ['AGENTS.md', *[str(x.relative_to(a.root)) for x in (a.root / 'skills').rglob('*.md')]])
current = [entry(path, read(path, a.candidate)) for path in sorted(current_paths) if corpus(path)]
current.append(entry('PREFERENCES.example.md', read('PREFERENCES.example.md', a.candidate)))
# Conservatively charge every added line of these changed documents, including
# native setup text beyond preference guidance. Removed pre-existing text earns
# no credit, and new instructions cannot disappear from the count by relocation.
supplement = []
for path in ['README.md', 'docs/opencode.md', 'GLOSSARY.md']:
    args = ['diff', '--no-ext-diff', '--unified=0', BASE]
    if a.candidate:
        args.append(a.candidate)
    diff = git(*args, '--', path).decode()
    additions = '\n'.join(line[1:] for line in diff.splitlines()
                           if line.startswith('+') and not line.startswith('+++'))
    item = entry(path, additions.encode())
    item['scope'] = 'all added lines versus baseline; removals earn no credit'
    item['candidate_file_sha256'] = hashlib.sha256(read(path, a.candidate)).hexdigest()
    item['added_text'] = additions
    supplement.append(item)
before = sum(x['words'] for x in original)
source = sum(x['words'] for x in current if x['path'] != 'PREFERENCES.example.md')
after = sum(x['words'] for x in current + supplement)
assert len(original) == 43 and before == 21466
print(json.dumps({'baseline': BASE, 'candidate': a.candidate or 'working tree',
                  'head': git('rev-parse', 'HEAD').decode().strip(),
                  'baseline_words': before, 'candidate_original_scope_words': source,
                  'original_scope_reduction_percent': round(100 * (before-source)/before, 2),
                  'candidate_scope_expanded_words': after,
                  'scope_expanded_reduction_percent': round(100*(before-after)/before, 2),
                  'baseline_inventory': original, 'candidate_inventory': current,
                  'additional_guidance': supplement}, indent=2))
