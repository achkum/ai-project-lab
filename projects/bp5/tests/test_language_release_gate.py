"""Adversarial release-evidence tests. Passing proofs exist only in temp fixtures."""
import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

BP5 = Path(__file__).resolve().parents[1]
ROOT = BP5.parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('bp5_language_gate_test', BP5/'check_language_acceptance.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class LanguageReleaseGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='bp5-gate-fixture-')
        self.root = Path(self.tmp.name)
        self.workspace = self.root/'candidate'; self.workspace.mkdir()
        self.models = self.root/'synthetic-runtime'; self.models.mkdir()
        for folder in ('server', 'content', 'web', 'deploy'):
            (self.workspace/folder).mkdir()
        files = {'server/run.py': 'pass\n', 'server/checker.py': 'def check(text):\n    return None\n',
                 'server/prompt.txt': 'Synthetic fixture only\n', 'server/requirements.txt': 'fixture==1\n',
                 'language-linux.lock': 'synthetic-runtime-fixture==1\n',
                 'deploy/Dockerfile': 'FROM fixture\n', 'web/app.js': '// fixture\n',
                 'deploy/activate.py': "def start():\n    values={'BP5_SEMANTIC_REQUIRED':'1'}\n",
                 'README.md': 'Synthetic fixture', 'PRODUCT.md': 'Synthetic fixture'}
        for name, text in files.items():
            (self.workspace/name).write_text(text, encoding='utf-8')
        product = {'delivery': 'vps_service', 'name': 'Prata', 'version': 3,
                   'entry': 'server/run.py', 'runtime': 'python', 'memory_mb': 1536}
        self.write('product.json', product)
        (self.models/'fixture-model.bin').write_bytes(b'NOT A REAL MODEL')
        self.declaration = {'schema_version': 1, 'adapter': {'entrypoint': 'server/checker.py:check',
            'configuration': {'threshold': 0.99, 'language_gate': 'fixture'}, 'execution_mode': 'production_adapter',
            'runtime_platform': 'linux', 'evaluation_target': 'identical_linux_container',
            'environment': {'BP5_SEMANTIC_REQUIRED': '1'}},
            'artifacts': [{'path': 'fixture-model.bin', 'sha256': gate.digest(b'NOT A REAL MODEL')}]}
        self.write(gate.DECLARATION, self.declaration)
        self.library = {'content_version': 'fixture-only-v1', 'situations': []}
        cases = []
        for index in range(54):
            level = ('basic', 'medium', 'high')[index//18]
            mid = 'fixture-task-'+str(index)
            self.library['situations'].append({'level': level, 'missions': [{'id': mid, 'steps': [
                {'id': 'choice', 'intents': [{'id': 'expected'}, {'id': 'wrong'}]}]}]})
            for n in range(3):
                for bucket in ('valid', 'negative'):
                    valid = bucket == 'valid'
                    long_reply = 36 <= index < 48 and (n < 2 if valid else n == 0)
                    cases.append({'case_id': f'{mid}-{bucket}-{n}', 'mission_id': mid, 'difficulty': level,
                        'bucket': bucket, 'expected_intent': 'expected' if valid else None,
                        'challenge_type': ('long_' if long_reply else '') + ('paraphrase' if valid else 'contradiction'),
                        'actual_intent': 'expected' if valid else None, 'advanced': valid,
                        'source': 'semantic' if valid else 'none', 'outcome': 'completed'})
        self.write('content/library.json', self.library)
        metadata = sorted([{k: row[k] for k in gate.METADATA_KEYS} for row in cases], key=lambda x: x['case_id'])
        self.policy = json.loads((BP5/'acceptance-contract.json').read_text(encoding='utf-8'))
        self.policy.update(model_root=str(self.models), active_corpus={
            'sha256': gate.digest(b'SYNTHETIC FULL FIXTURE CORPUS'), 'metadata_sha256': gate.digest(gate.canonical(metadata)),
            'total': 324, 'valid': 162, 'negative': 162, 'mission_count': 54, 'independent_evaluator_id': 'fixture-reviewer',
            'long_suite': {'valid': 24, 'negative': 12, 'mission_count': 12}})
        self.report = {'schema_version': 1, 'suite': 'bp5-language-acceptance', 'evaluation_id': 'fixture-never-real',
            'created_at_utc': '2026-11-01T00:00:00Z',
            'evaluator': {'id': 'fixture-reviewer', 'role': 'independent_acceptance', 'independent': True,
                          'case_selection': 'full_frozen_corpus', 'production_adapter': True},
            'corpus': {k: self.policy['active_corpus'][k] for k in ('sha256', 'metadata_sha256')},
            'candidate': gate.candidate_binding(self.workspace, str(self.models))[0], 'results': cases}
        self.policy_path = self.root/'trusted-test-policy.json'
        self.pin()

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, value):
        (self.workspace/name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    def pin(self):
        self.write('LANGUAGE_ACCEPTANCE.json', self.report)
        self.policy['accepted_report_sha256'] = gate.digest((self.workspace/'LANGUAGE_ACCEPTANCE.json').read_bytes())
        self.policy_path.write_text(json.dumps(self.policy), encoding='utf-8')

    def check(self):
        return gate.require_acceptance(self.workspace, self.policy_path)

    def test_real_contract_is_unpinned_and_candidate_contract_cannot_self_approve(self):
        self.assertEqual(self.check()['valid_correct'], 162)
        self.write('acceptance-contract.json', self.policy)
        with self.assertRaisesRegex(RuntimeError, 'no independently accepted report'):
            gate.require_acceptance(self.workspace)

    def test_report_missing_or_changed_after_pin_blocks(self):
        (self.workspace/'LANGUAGE_ACCEPTANCE.json').unlink()
        with self.assertRaisesRegex(RuntimeError, 'required file missing'): self.check()
        self.pin()
        self.report['results'][0]['actual_intent'] = 'wrong'
        self.write('LANGUAGE_ACCEPTANCE.json', self.report)
        with self.assertRaisesRegex(RuntimeError, 'independently pinned'): self.check()

    def test_source_prompt_dependency_library_adapter_and_model_changes_invalidate(self):
        for name in ('server/checker.py', 'server/prompt.txt', 'server/requirements.txt', 'language-linux.lock', 'deploy/Dockerfile', 'web/app.js'):
            with self.subTest(path=name):
                p = self.workspace/name; original = p.read_bytes(); p.write_bytes(original+b'\nchanged')
                with self.assertRaisesRegex(RuntimeError, 'stale checker'): self.check()
                p.write_bytes(original)
        self.library['content_version'] = 'new-unreviewed-version'; self.write('content/library.json', self.library)
        with self.assertRaisesRegex(RuntimeError, 'stale checker'): self.check()
        self.library['content_version'] = 'fixture-only-v1'; self.write('content/library.json', self.library)
        self.declaration['adapter']['configuration']['threshold'] = 0.1; self.write(gate.DECLARATION, self.declaration)
        with self.assertRaisesRegex(RuntimeError, 'stale checker'): self.check()
        self.declaration['adapter']['configuration']['threshold'] = 0.99; self.write(gate.DECLARATION, self.declaration)
        (self.models/'fixture-model.bin').write_bytes(b'CHANGED MODEL')
        with self.assertRaisesRegex(RuntimeError, 'artifact bytes changed'): self.check()

    def test_lf_crlf_equivalence_and_new_runtime_file_detection(self):
        for row in self.report['candidate']['source_files']:
            p = self.workspace/row['path']; p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
        self.assertEqual(self.check()['valid_correct'], 162)
        (self.workspace/'server/unreviewed_prompt.json').write_text('{}')
        with self.assertRaisesRegex(RuntimeError, 'stale checker'): self.check()

    def test_hand_selected_relabelled_duplicate_and_wrong_evaluator_rejected(self):
        original = copy.deepcopy(self.report)
        for mutation in ('subset', 'duplicate', 'relabel', 'self-review'):
            with self.subTest(mutation=mutation):
                self.report = copy.deepcopy(original)
                if mutation == 'subset': self.report['results'].pop()
                if mutation == 'duplicate': self.report['results'][1] = dict(self.report['results'][0])
                if mutation == 'relabel': self.report['results'][0]['challenge_type'] = 'hand-selected-easy'
                if mutation == 'self-review': self.report['evaluator']['id'] = 'implementer'
                self.pin()
                with self.assertRaises(RuntimeError): self.check()

    def test_manual_or_unavailable_does_not_count_even_with_self_reported_perfect_score(self):
        original = copy.deepcopy(self.report)
        for source in ('manual', 'unavailable'):
            self.report = copy.deepcopy(original)
            self.report['summary'] = {'valid_accuracy': 1.0, 'passed': True}
            for row in self.report['results']:
                if row['bucket'] == 'valid':
                    row['source'] = source
                    if source == 'unavailable': row.update(advanced=False, outcome='unavailable')
            self.pin()
            with self.assertRaisesRegex(RuntimeError, 'below90'): self.check()

    def test_one_wrong_intent_or_negative_advance_blocks_release(self):
        original = copy.deepcopy(self.report)
        for bucket in ('valid', 'negative'):
            self.report = copy.deepcopy(original)
            row = next(x for x in self.report['results'] if x['bucket'] == bucket)
            row.update(advanced=True, actual_intent='wrong', source='semantic')
            self.pin()
            with self.assertRaisesRegex(RuntimeError, 'advance'): self.check()

    def test_unavailable_negative_cases_cannot_masquerade_as_safe_rejections(self):
        row = next(x for x in self.report['results'] if x['bucket']=='negative')
        row.update(source='unavailable', outcome='unavailable')
        self.pin()
        with self.assertRaisesRegex(RuntimeError, 'not automatically evaluated'): self.check()

    def test_standalone_adapter_or_disabled_deployment_cannot_qualify(self):
        self.declaration['adapter']['runtime_platform'] = 'windows'
        self.write(gate.DECLARATION, self.declaration)
        with self.assertRaisesRegex(RuntimeError, 'deployment Linux runtime'): self.check()
        self.declaration['adapter']['runtime_platform'] = 'linux'
        self.declaration['adapter']['environment']['BP5_SEMANTIC_REQUIRED'] = '0'
        self.write(gate.DECLARATION, self.declaration)
        with self.assertRaisesRegex(RuntimeError, 'evaluation must enable'): self.check()
        self.declaration['adapter']['environment']['BP5_SEMANTIC_REQUIRED'] = '1'
        self.write(gate.DECLARATION, self.declaration)
        (self.workspace/'deploy/activate.py').write_text("def start():\n    values={'BP5_SEMANTIC_REQUIRED':'0'}\n")
        with self.assertRaisesRegex(RuntimeError, 'deployment does not enable'): self.check()

    def test_overall_pass_cannot_hide_weak_difficulty(self):
        for row in [x for x in self.report['results'] if x['bucket']=='valid' and x['difficulty']=='high'][:9]:
            row.update(advanced=False, actual_intent=None, source='none')
        self.pin()
        with self.assertRaisesRegex(RuntimeError, 'high automatic accuracy below85'): self.check()

    def test_corpus_rotation_invalidates_old_report(self):
        self.policy['active_corpus']['sha256'] = gate.digest(b'NEW INDEPENDENT CORPUS')
        self.policy['accepted_report_sha256'] = None
        self.policy_path.write_text(json.dumps(self.policy))
        with self.assertRaisesRegex(RuntimeError, 'no independently accepted report'): self.check()

    def test_overall_and_high_pass_cannot_hide_long_reply_failures(self):
        long_rows = [x for x in self.report['results'] if x['bucket']=='valid' and x['challenge_type'].startswith('long_')]
        self.assertEqual(len(long_rows), 24)
        for row in long_rows[:3]: row.update(advanced=False, actual_intent=None, source='none')
        self.pin()
        with self.assertRaisesRegex(RuntimeError, 'long reply automatic accuracy below90'): self.check()

    def test_private_artifact_location_is_portable_but_bytes_still_bound(self):
        self.policy['model_root'] = None; self.pin()
        with patch.dict('os.environ', {'BP5_ACCEPTANCE_ARTIFACT_ROOT': str(self.models)}):
            self.assertEqual(self.check()['long_replies'], {'correct': 24, 'valid': 24, 'negative': 12})
            (self.models/'fixture-model.bin').write_bytes(b'WRONG BYTES AT OPERATOR PATH')
            with self.assertRaisesRegex(RuntimeError, 'artifact bytes changed'): self.check()

    def test_delivery_checks_and_direct_vps_contract_cannot_bypass_real_gate(self):
        from engine.product_delivery import check_product, contract
        # A candidate-local passing proof/policy is not the canonical trust pin.
        self.write('acceptance-contract.json', self.policy)
        with self.assertRaisesRegex(RuntimeError, 'no independently accepted report'):
            contract(self.workspace, 'vps_service')
        with patch('engine.product_delivery.sp.Popen') as spawn:
            with self.assertRaisesRegex(RuntimeError, 'no independently accepted report'):
                check_product(self.workspace, 'vps_service')
            spawn.assert_not_called()
        from engine.vps_product_delivery import deploy
        with patch('engine.vps_product_delivery.command') as network:
            with self.assertRaisesRegex(RuntimeError, 'no independently accepted report'):
                deploy({'runtime_root': str(self.root/'unused-runtime')},
                       {'id': 'fixture-only', 'scope': {'id': 'BP5', 'version': 3}}, self.workspace)
            network.assert_not_called()

    def test_unrelated_local_delivery_still_executes_ordinary_acceptance(self):
        from engine.product_delivery import check_product
        product = json.loads((self.workspace/'product.json').read_text())
        product.update(name='Unrelated fixture', delivery='local_service')
        self.write('product.json', product)
        (self.workspace/'tests').mkdir()
        (self.workspace/'tests/test_fixture.py').write_text(
            'import unittest\nclass Fixture(unittest.TestCase):\n def test_real_check(self): self.assertEqual(2+2,4)\n')
        self.assertEqual(check_product(self.workspace, 'local_service')['name'], 'Unrelated fixture')


if __name__ == '__main__':
    unittest.main()
