"""Fail-closed BP5 release proof verifier. Never opens hidden acceptance texts.

Trust anchor: this canonical checkout's acceptance-contract.json, not a contract
supplied by a generated candidate. Coordinator pins independently produced report
bytes only after evaluation. It is not tamper-proof against a trusted repo editor.
"""
import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path, PurePosixPath

CONTRACT = Path(__file__).with_name('acceptance-contract.json')
DECLARATION = 'LANGUAGE_CHECKER_MANIFEST.json'
LEVELS = {'basic', 'medium', 'high'}
AUTOMATIC_SOURCES = {'authored', 'semantic'}
SOURCES = AUTOMATIC_SOURCES | {'unavailable', 'manual', 'none'}
METADATA_KEYS = ('case_id', 'mission_id', 'difficulty', 'bucket', 'expected_intent', 'challenge_type')
MAX_JSON = 8 * 1024 * 1024
ROOT_INPUTS = {'product.json', '.dockerignore', 'requirements.txt', 'requirements.lock', 'language-linux.lock', DECLARATION}
SKIP_DIRS = {'tests', '__pycache__', 'snapshots', 'data', 'runtime', '.venv', 'node_modules'}


def require(condition, message):
    if not condition:
        raise RuntimeError('BP5 language acceptance: ' + message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def sha(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


def relative_name(value):
    require(isinstance(value, str) and value and '\\' not in value and ':' not in value, 'invalid relative path')
    p = PurePosixPath(value)
    require(not p.is_absolute() and all(x not in ('', '.', '..') for x in value.split('/')), 'unsafe relative path')
    return value


def checked_file(root, name):
    name = relative_name(name)
    root = Path(root).absolute()
    p = root / name
    require(all(not x.is_symlink() and not getattr(x, 'is_junction', lambda: False)() for x in (p, *p.parents)), 'linked proof/source path')
    require(p.is_file() and p.resolve().is_relative_to(root.resolve()), 'required file missing: ' + name)
    require(p.stat().st_nlink == 1, 'hardlinked proof/source file')
    return p


def file_bytes(path, limit=MAX_JSON):
    before = path.stat()
    require(before.st_size <= limit, 'file exceeds size bound: ' + path.name)
    raw = path.read_bytes()
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), 'file changed while checking')
    return raw


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'duplicate JSON field')
        obj[key] = value
    return obj


def parse_json(raw):
    try:
        return json.loads(raw.decode('utf-8-sig'), object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))
    except (UnicodeError, ValueError) as exc:
        raise RuntimeError('BP5 language acceptance: malformed JSON proof') from exc


def text_hash(raw):
    # Same source on Windows/Linux has the same identity. No whitespace folding.
    return digest(raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n').encode('utf-8'))


def source_manifest(workspace):
    workspace = Path(workspace)
    paths = set(ROOT_INPUTS)
    for folder in ('server', 'content', 'web', 'deploy'):
        base = workspace / folder
        require(base.is_dir(), 'runtime source directory missing: ' + folder)
        for p in base.rglob('*'):
            rel = p.relative_to(workspace)
            if any(x in SKIP_DIRS or x.startswith('.') for x in rel.parts):
                continue
            if p.name.startswith('test_') or p.name.endswith(('.test.cjs', '.pyc', '.log')):
                continue
            if p.is_file() or p.is_symlink():
                paths.add(rel.as_posix())
    rows = []
    total = 0
    for name in sorted(paths):
        if name in ROOT_INPUTS and not (workspace / name).exists():
            continue
        p = checked_file(workspace, name)
        raw = file_bytes(p, 20 * 1024 * 1024)
        total += len(raw)
        require(total <= 40 * 1024 * 1024, 'runtime source manifest exceeds bound')
        try:
            value, encoding = text_hash(raw), 'utf8-lf'
        except UnicodeError:
            value, encoding = digest(raw), 'raw'
        rows.append({'path': name, 'sha256': value, 'encoding': encoding})
    return rows


def artifact_hash(path):
    before = path.stat()
    require(0 < before.st_size <= 8 * 1024**3, 'invalid runtime artifact size')
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    after = path.stat()
    require((before.st_size, before.st_mtime_ns, before.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino), 'runtime artifact changed while checking')
    return h.hexdigest()


def candidate_binding(workspace, model_root):
    manifest = source_manifest(workspace)
    declaration = parse_json(file_bytes(checked_file(workspace, DECLARATION)))
    require(declaration.get('schema_version') == 1, 'checker declaration schema required')
    adapter = declaration.get('adapter', {})
    require(adapter.get('execution_mode') == 'production_adapter', 'evaluated production adapter required')
    require(adapter.get('runtime_platform') == 'linux' and adapter.get('evaluation_target') in
            {'isolated_vps_candidate', 'identical_linux_container'}, 'acceptance must evaluate the deployment Linux runtime')
    require(isinstance(adapter.get('environment'), dict) and adapter['environment'].get('BP5_SEMANTIC_REQUIRED') == '1',
            'evaluation must enable the required production language checker')
    # The managed deployer uses this explicit values dictionary. A good standalone
    # model result must not authorize deployment with the old matcher still active.
    deploy_source = file_bytes(checked_file(workspace, 'deploy/activate.py')).decode('utf-8-sig')
    tree = ast.parse(deploy_source)
    values = [node.value for fn in tree.body if isinstance(fn, ast.FunctionDef) and fn.name == 'start'
              for node in fn.body if isinstance(node, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == 'values' for t in node.targets)
              and isinstance(node.value, ast.Dict)]
    flags = [value.value for mapping in values for key, value in zip(mapping.keys, mapping.values)
             if isinstance(key, ast.Constant) and key.value == 'BP5_SEMANTIC_REQUIRED' and isinstance(value, ast.Constant)]
    require(flags == ['1'], 'managed deployment does not enable the required production language checker')
    entry = adapter.get('entrypoint', '')
    require(isinstance(entry, str) and ':' in entry, 'adapter entrypoint required')
    module, function = entry.rsplit(':', 1)
    require(module.startswith('server/') and re.fullmatch(r'[A-Za-z_]\w*', function), 'invalid adapter entrypoint')
    checked_file(workspace, module)
    require(module in {row['path'] for row in manifest}, 'adapter implementation must be in bound runtime sources')
    require(isinstance(adapter.get('configuration'), dict), 'evaluated adapter configuration required')
    artifacts = declaration.get('artifacts')
    require(isinstance(artifacts, list) and 0 < len(artifacts) <= 1024, 'pinned inference artifacts required')
    require(isinstance(model_root, str) and model_root, 'trusted runtime artifact root not configured')
    seen = set()
    for item in artifacts:
        require(isinstance(item, dict) and set(item) == {'path', 'sha256'}, 'invalid artifact declaration')
        name = relative_name(item['path'])
        require(name not in seen and sha(item['sha256']), 'duplicate/unpinned runtime artifact')
        seen.add(name)
        require(artifact_hash(checked_file(Path(model_root), name)) == item['sha256'], 'runtime artifact bytes changed: ' + name)
    library_raw = file_bytes(checked_file(workspace, 'content/library.json'), 20 * 1024 * 1024)
    library = parse_json(library_raw)
    require(isinstance(library.get('content_version'), str) and library['content_version'], 'library semantic version missing')
    binding = {'source_files': manifest, 'source_sha256': digest(canonical(manifest)),
               'library': {'version': library['content_version'], 'sha256': text_hash(library_raw)},
               'adapter_sha256': digest(canonical(adapter)), 'artifacts': artifacts}
    return binding, library


def score_report(report, policy, library):
    corpus = policy['active_corpus']
    evaluator = report.get('evaluator', {})
    require(evaluator.get('id') == corpus['independent_evaluator_id'] and evaluator.get('role') == 'independent_acceptance'
            and evaluator.get('independent') is True and evaluator.get('case_selection') == 'full_frozen_corpus'
            and evaluator.get('production_adapter') is True, 'independent full-corpus production evaluation required')
    require(report.get('corpus') == {'sha256': corpus['sha256'], 'metadata_sha256': corpus['metadata_sha256']}, 'unapproved corpus')
    rows = report.get('results')
    require(isinstance(rows, list) and len(rows) == corpus['total'], 'full frozen corpus results required')
    missions = {m['id']: (sit['level'], {i['id'] for s in m['steps'] for i in s['intents']})
                for sit in library['situations'] for m in sit['missions']}
    require(len(missions) == 54 and corpus['mission_count'] == 54, 'all54 task coverage required')
    metadata, seen, covered, valid, correct = [], set(), set(), [], []
    valid_missions, negative_missions = set(), set()
    long_correct, long_valid, long_negative, long_missions = 0, 0, 0, set()
    per_level = {level: [0, 0] for level in LEVELS}
    for row in rows:
        require(isinstance(row, dict) and all(k in row for k in METADATA_KEYS), 'case metadata incomplete')
        cid, mid, level = row['case_id'], row['mission_id'], row['difficulty']
        require(isinstance(cid, str) and cid and cid not in seen, 'case IDs must be unique')
        require(mid in missions and level in LEVELS and level == missions[mid][0], 'invalid mission/difficulty')
        seen.add(cid); covered.add(mid)
        expected, actual = row['expected_intent'], row.get('actual_intent')
        require(expected is None or expected in missions[mid][1], 'invalid expected intent')
        require(actual is None or isinstance(actual, str) and actual in missions[mid][1], 'invalid evaluated intent')
        require('actual_intent' in row and type(row.get('advanced')) is bool and row.get('source') in SOURCES
                and row.get('outcome') in {'completed', 'unavailable', 'error'}, 'evaluated adapter result incomplete')
        require(isinstance(row['challenge_type'], str) and row['challenge_type'], 'challenge category required')
        is_long = row['challenge_type'].startswith('long_')
        if is_long:
            require(level == 'high', 'long reply must be in the High suite')
            long_missions.add(mid)
        metadata.append({k: row[k] for k in METADATA_KEYS})
        if row['bucket'] == 'valid':
            require(expected is not None, 'valid case has no expected intent')
            valid.append(row)
            valid_missions.add(mid)
            ok = row['advanced'] and actual == expected and row['source'] in AUTOMATIC_SOURCES and row['outcome'] == 'completed'
            correct.append(ok)
            per_level[level][0] += int(ok); per_level[level][1] += 1
            if is_long:
                long_valid += 1; long_correct += int(ok)
            require(not row['advanced'] or actual == expected, 'wrong-intent advance')
        else:
            require(row['bucket'] == 'negative' and expected is None, 'invalid negative case')
            negative_missions.add(mid)
            if is_long: long_negative += 1
            require(not row['advanced'], 'negative/contradiction/off-topic advance')
            require(row['outcome'] == 'completed' and row['source'] in AUTOMATIC_SOURCES | {'none'},
                    'negative case was not automatically evaluated; unavailable/manual is not correct')
        require(not row['advanced'] or row['outcome'] == 'completed', 'unavailable/error cannot advance')
    require(digest(canonical(sorted(metadata, key=lambda r: r['case_id']))) == corpus['metadata_sha256'], 'frozen case metadata changed or hand-selected')
    require(covered == set(missions), 'not all54 tasks evaluated')
    require(valid_missions == set(missions) and negative_missions == set(missions), 'valid and negative coverage required for every task')
    require(len(valid) == corpus['valid'] and len(rows)-len(valid) == corpus['negative']
            and len(valid) >= 120 and len(rows)-len(valid) >= 120, 'insufficient/mismatched valid or negative coverage')
    require(sum(correct)*100 >= len(valid)*90, 'automatic correct valid replies below90percent')
    for level, (hits, total) in per_level.items():
        require(total > 0 and hits*100 >= total*85, level + ' automatic accuracy below85percent')
    subgroup = corpus.get('long_suite', {})
    require(isinstance(subgroup, dict) and set(subgroup) == {'valid', 'negative', 'mission_count'}
            and all(type(subgroup[k]) is int for k in subgroup)
            and subgroup['valid'] >= 24 and subgroup['negative'] >= 12 and subgroup['mission_count'] >= 12,
            'independently frozen long reply coverage required')
    require(long_valid == subgroup['valid'] and long_negative == subgroup['negative']
            and len(long_missions) == subgroup['mission_count'], 'long reply subgroup coverage changed')
    require(long_correct*100 >= long_valid*90, 'long reply automatic accuracy below90percent')
    return {'valid_correct': sum(correct), 'valid_total': len(valid), 'negative_total': len(rows)-len(valid),
            'long_replies': {'correct': long_correct, 'valid': long_valid, 'negative': long_negative},
            'per_difficulty': {k: {'correct': v[0], 'total': v[1]} for k, v in per_level.items()}}


def require_acceptance(workspace, policy_path=CONTRACT):
    workspace = Path(workspace).absolute()
    policy_path = Path(policy_path).absolute()
    policy_raw = file_bytes(checked_file(policy_path.parent, policy_path.name))
    policy = parse_json(policy_raw)
    require(policy.get('schema_version') == 1 and policy.get('product') == 'BP5', 'trusted policy invalid')
    # Hard floors cannot be weakened through a candidate declaration/report.
    require(policy.get('thresholds') == {'valid_percent': 90, 'each_difficulty_percent': 85,
            'max_wrong_intent_advances': 0, 'max_negative_advances': 0, 'minimum_valid': 120, 'minimum_negative': 120}, 'release thresholds changed')
    require(sha(policy.get('accepted_report_sha256')), 'no independently accepted report is pinned; release remains blocked')
    corpus = policy.get('active_corpus', {})
    require(sha(corpus.get('sha256')) and sha(corpus.get('metadata_sha256')), 'independent corpus freeze incomplete')
    require(policy.get('report_file') == 'LANGUAGE_ACCEPTANCE.json', 'unexpected report location')
    raw = file_bytes(checked_file(workspace, policy['report_file']))
    require(digest(raw) == policy['accepted_report_sha256'], 'report bytes are not the independently pinned report')
    report = parse_json(raw)
    require(report.get('schema_version') == 1 and report.get('suite') == 'bp5-language-acceptance', 'report schema invalid')
    require(isinstance(report.get('evaluation_id'), str) and report['evaluation_id'], 'evaluation identity missing')
    require(isinstance(report.get('created_at_utc'), str) and report['created_at_utc'], 'evaluation timestamp missing')
    # The operator chooses where to read the exact pinned Linux bytes. Their
    # local filesystem location is not proof identity and need not be published.
    model_root = os.environ.get('BP5_ACCEPTANCE_ARTIFACT_ROOT') or policy.get('model_root')
    binding, library = candidate_binding(workspace, model_root)
    require(report.get('candidate') == binding, 'stale checker/prompt/library/adapter/model proof')
    result = score_report(report, policy, library)
    # Catch candidate/report/contract mutation during the verification itself.
    require(source_manifest(workspace) == binding['source_files'], 'candidate changed during verification')
    require(file_bytes(checked_file(workspace, policy['report_file'])) == raw, 'report changed during verification')
    require(file_bytes(checked_file(policy_path.parent, policy_path.name)) == policy_raw, 'trusted policy changed during verification')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workspace', nargs='?', default=str(Path(__file__).parent))
    args = parser.parse_args()
    try:
        print(json.dumps({'ok': True, **require_acceptance(args.workspace)}, sort_keys=True))
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        parser.exit(1, str(exc) + '\n')
