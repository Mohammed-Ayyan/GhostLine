import urllib.request
import json
from pathlib import Path

repo = 'Mohammed-Ayyan/GhostLine'
base_url = f'https://api.github.com/repos/{repo}'
headers = {'User-Agent': 'Ghostline-Audit/1.0'}

def get_json(endpoint):
    req = urllib.request.Request(f'{base_url}{endpoint}', headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as e:
        return {'error': str(e)}

repo_info = get_json('')
branches = get_json('/branches')
tags = get_json('/tags')
releases = get_json('/releases')
prs = get_json('/pulls?state=all')
issues = get_json('/issues?state=open')

lines = [
    '# Ghostline — GitHub Remote Audit',
    '',
    f'- **Repository:** {repo}',
    f'- **Visibility:** {repo_info.get("visibility", "unknown")}',
    f'- **Default Branch:** {repo_info.get("default_branch", "main")}',
    f'- **Open Issues Count:** {repo_info.get("open_issues_count", 0)}',
    '',
    '## Remote Branches',
]
if isinstance(branches, list):
    for b in branches:
        lines.append(f'- `{b.get("name")}` (commit: `{b.get("commit", {}).get("sha", "")[:7]}`)')
else:
    lines.append(f'- Could not list branches: {branches}')

lines.extend(['', '## Remote Tags'])
if isinstance(tags, list) and tags:
    for t in tags:
        lines.append(f'- `{t.get("name")}` (commit: `{t.get("commit", {}).get("sha", "")[:7]}`)')
else:
    lines.append('- 0 tags found')

lines.extend(['', '## Remote Releases'])
if isinstance(releases, list) and releases:
    for r in releases:
        lines.append(f'- `{r.get("tag_name")}`: {r.get("name")} (published: {r.get("published_at")})')
else:
    lines.append('- 0 releases found')

lines.extend(['', '## Pull Requests'])
if isinstance(prs, list) and prs:
    for p in prs:
        lines.append(f'- #{p.get("number")}: {p.get("title")} ({p.get("state")})')
else:
    lines.append('- 0 pull requests found')

out_path = Path('reports/run9/github_audit.md')
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('Audit written to', out_path)
print('\n'.join(lines))
