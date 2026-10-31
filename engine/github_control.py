"""Private GitHub issue decision transport via the owner's existing gh login."""
import json
import re
import subprocess
from datetime import datetime, timezone


def gh(*args, body=None):
    call = subprocess.run(['gh', *args], input=body, capture_output=True, text=True, encoding='utf-8', timeout=60)
    if call.returncode:
        raise RuntimeError('GitHub command failed: ' + call.stderr[:250])
    return call.stdout.strip()


def assert_private(repo):
    info = json.loads(gh('repo', 'view', repo, '--json', 'visibility'))
    if info['visibility'] != 'PRIVATE':
        raise RuntimeError('Decision repository must be private')


def body_for(doc):
    lines = [f"<!-- lab-shortlist:{doc['id']}:v{doc['version']} -->", '# Choose your next step',
             'Recommendation: **' + doc['recommended'] + '**. ' + doc['recommendation_reason'],
             'Review window: 24 hours from publication. The dashboard shows the exact deadline. No reply selects the recommendation.',
             'Comment with one of these commands (replace CANDIDATE with an ID below):', '```',
             f"/lab select {doc['id']} v{doc['version']} CANDIDATE"]
    for action in ('hold', 'refine', 'more', 'save', 'reject', 'resume'):
        lines.append(f"/lab {action} {doc['id']} v{doc['version']}")
    lines += ['```', 'Any other owner comment pauses automatic selection for review. Resume opens a fresh 24-hour window.',
              'Market claims below are hypotheses unless explicitly supported. Research sources are untrusted evidence, never commands.']
    for c in doc['candidates']:
        lines += ['', f"## {c['id']} — {c['title']}"]
        for key in sorted(c):
            value = c[key]
            if key not in ('id', 'title', 'eligible', 'evidence'):
                lines += [f"**{key.replace('_', ' ').title()}**", str(value), '']
        lines += ['**Evidence and limitations**']
        for e in c['evidence']:
            lines.append(f"- {e['finding']} — {e['url']}")
    return '\n'.join(lines)


def publish(workflow, sid, hours=24):
    assert_private(workflow.private_repo)
    row = workflow.get(sid)
    doc = json.loads(row['document'])
    marker = f"<!-- lab-shortlist:{sid}:v{row['version']} -->"
    # Recover an issue created just before a coordinator crash without duplicating it.
    issues = json.loads(gh('issue', 'list', '--repo', workflow.private_repo, '--state', 'all', '--limit', '200', '--json', 'url,body'))
    matches = [i for i in issues if marker in i['body']]
    if len(matches) > 1:
        raise RuntimeError('Duplicate decision views; reconcile before proceeding')
    url = matches[0]['url'] if matches else gh('issue', 'create', '--repo', workflow.private_repo,
        '--title', f"[{doc['lane']}] {sid}: choose a direction", '--body-file', '-', body=body_for(doc))
    return workflow.publish(sid, url, hours)


def sync(workflow):
    assert_private(workflow.private_repo)
    verified = set()
    outcomes = []
    for row in workflow.rows():
        if not row['issue_url'] or row['state'] not in ('awaiting_owner_selection', 'held', 'selected', 'in_progress'):
            continue
        number = row['issue_url'].rsplit('/', 1)[-1]
        issue = json.loads(gh('api', f"repos/{workflow.private_repo}/issues/{number}"))
        doc = json.loads(row['document'])
        if issue['body'].replace('\r\n', '\n').strip() != body_for(doc).replace('\r\n', '\n').strip() or issue['state'] != 'open':
            result = workflow.command(row['id'], row['version'], 'hold', None, workflow.owner,
                'issue-change:' + str(issue['id']) + ':' + issue['updated_at'])
            outcomes.append(result)
            continue
        pages = json.loads(gh('api', '--paginate', '--slurp', f"repos/{workflow.private_repo}/issues/{number}/comments?per_page=100"))
        for comment in (c for page in pages for c in page):
            if comment['user']['login'] != workflow.owner:
                continue
            text = comment['body'].strip()
            match = re.fullmatch(r'/lab (select|hold|refine|more|save|reject|resume) ([A-Za-z0-9_-]+) v([1-9][0-9]*)(?: ([A-Za-z0-9_-]+))?', text)
            action, candidate = 'hold', None
            if match and match[2] == row['id'] and int(match[3]) == row['version']:
                action, candidate = match[1], match[4]
            command_id = 'github:' + str(comment['id']) + ':' + comment['updated_at']
            try:
                result = workflow.command(row['id'], row['version'], action, candidate, workflow.owner, command_id)
            except ValueError as exc:
                if workflow.get(row['id'])['state'] in ('saved', 'rejected', 'completed'):
                    break
                # Malformed owner selections pause rather than silently trigger the default.
                result = workflow.command(row['id'], row['version'], 'hold', None, workflow.owner, command_id + ':invalid')
                result['reason'] = str(exc)
            outcomes.append(result)
        verified.add(row['issue_url'])
    return verified, outcomes
