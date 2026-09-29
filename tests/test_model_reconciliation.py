"""Fail-closed checks for retained model evidence and public-census identity."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = ROOT / 'examples/estate-audit-20260924'
spec = importlib.util.spec_from_file_location('verify_model_reconciliation', ROOT / 'tools/verify_model_reconciliation.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class ModelReconciliationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads((FIXTURE_ROOT / 'data/reconciliation/model_decisions.json').read_text(encoding='utf-8'))

    def check_mutation(self, mutate, expected):
        document = copy.deepcopy(self.document)
        mutate(document)
        self.assertTrue(any(expected in error for error in module.validate(FIXTURE_ROOT, document)), expected)

    def test_exact_retained_evidence_verifies(self):
        self.assertEqual(module.validate(FIXTURE_ROOT, self.document), [])

    def test_removed_model_fails_coverage(self):
        self.check_mutation(lambda d: d['decisions'].pop(), 'DECISION_CENSUS')

    def test_duplicate_model_fails(self):
        self.check_mutation(lambda d: d['decisions'].__setitem__(0, copy.deepcopy(d['decisions'][1])), 'DUPLICATE_IDENTITY')

    def test_model_revision_cannot_drift(self):
        self.check_mutation(lambda d: d['decisions'][0].__setitem__('observed_revision', 'a' * 40), 'REVISION_MISMATCH')

    def test_retained_evidence_cannot_promote_model(self):
        self.check_mutation(lambda d: d['decisions'][0].__setitem__('production_qualified', True), 'PROMOTION_FORBIDDEN')

    def test_inference_claim_requires_runtime_witness(self):
        self.check_mutation(lambda d: d['decisions'][0].__setitem__('load_and_inference_verified', True), 'INFERENCE_BINDING')

    def test_training_hash_mismatch_cannot_be_hidden(self):
        def mutate(d):
            row = next(r for r in d['decisions'] if r['repository'] == 'SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3')
            row['training_receipt_hash_matches'] = True
        self.check_mutation(mutate, 'TRAINING_HASH_MISMATCH_HIDDEN')

    def test_retained_digest_tampering_fails(self):
        self.check_mutation(lambda d: d['input_bindings']['provider_sizes.json'].__setitem__('sha256', '0' * 64), 'EVIDENCE_DIGEST_MISMATCH')

    def test_paths_cannot_escape_root_or_use_windows_drive(self):
        for path in ('../outside.json', 'C:/secret.json', '/etc/passwd', '..\\outside.json'):
            with self.subTest(path=path):
                self.check_mutation(lambda d: d['input_bindings']['provider_sizes.json'].__setitem__('path', path), 'EVIDENCE_PATH_')

    def test_downloaded_byte_hash_cannot_be_replaced(self):
        def mutate(d):
            row = next(r for r in d['decisions'] if r['verified_artifact_bytes'])
            row['verified_artifact_bytes'][0]['sha256'] = 'a' * 64
        self.check_mutation(mutate, 'BYTE_BINDING')

    def test_file_length_is_bound(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            payload = b'{}'
            (root / 'evidence.json').write_bytes(payload)
            with self.assertRaisesRegex(ValueError, 'LENGTH'):
                module._read(root, {'path': 'evidence.json', 'sha256': hashlib.sha256(payload).hexdigest(), 'bytes': 5})

    def test_aggregate_counts_cannot_inflate(self):
        self.check_mutation(lambda d: d['coverage'].__setitem__('local_inference_verified', 49), 'COVERAGE_INFERENCE')

    def test_source_card_revision_must_match_the_model_revision(self):
        self.check_mutation(lambda d: d['decisions'][0]['evidence'][0].__setitem__('revision', 'f' * 40), 'SOURCE_CARD_REVISION')

    def test_source_card_url_must_name_the_exact_model_and_revision(self):
        for url in ('https://huggingface.co/SZLHOLDINGS/other/resolve/' + 'f' * 40 + '/README.md',
                    self.document['decisions'][0]['evidence'][0]['url'] + '?download=true',
                    self.document['decisions'][0]['evidence'][0]['url'].replace('/README.md', '/config.json')):
            with self.subTest(url=url):
                self.check_mutation(lambda d: d['decisions'][0]['evidence'][0].__setitem__('url', url), 'SOURCE_CARD_URL')

    def test_source_card_path_cannot_change(self):
        self.check_mutation(lambda d: d['decisions'][0]['evidence'][0].__setitem__('source_path', 'config.json'), 'SOURCE_CARD_PATH')

    def test_another_models_card_is_not_classification_evidence(self):
        def mutate(d):
            d['decisions'][0]['evidence'][0] = copy.deepcopy(d['decisions'][1]['evidence'][0])
        self.check_mutation(mutate, 'SOURCE_CARD_URL')

    def test_relabeling_another_models_card_still_fails_provider_byte_binding(self):
        def mutate(d):
            binding, donor = d['decisions'][0]['evidence'][0], d['decisions'][1]['evidence'][0]
            for name in ('path', 'sha256', 'bytes'):
                binding[name] = donor[name]
        self.check_mutation(mutate, 'SOURCE_CARD_PROVIDER_DIGEST')

    def test_card_kind_cannot_be_erased_to_bypass_identity_checks(self):
        self.check_mutation(lambda d: d['decisions'][0]['evidence'][0].pop('kind'), 'SOURCE_CARD_CARDINALITY')

    def test_census_cardinality_tracks_inputs_instead_of_hardcoding_49(self):
        document = copy.deepcopy(self.document)
        removed = document['decisions'].pop(0)
        self.assertFalse(removed['verified_artifact_bytes'])
        coverage = document['coverage']
        coverage['repositories'] = len(document['decisions'])
        coverage['by_artifact_kind'] = dict(Counter(row['artifact_kind'] for row in document['decisions']))
        original_read = module._read

        def changed_census(root, binding):
            value = original_read(root, binding)
            if binding == document['snapshot_binding']:
                return [row for row in value if row['path'] != removed['repository']]
            if binding == document['input_bindings']['provider_sizes.json']:
                value['models'] = [row for row in value['models'] if row['repository'] != removed['repository']]
            return value

        with mock.patch.object(module, '_read', side_effect=changed_census):
            self.assertEqual(module.validate(FIXTURE_ROOT, document), [])


if __name__ == '__main__':
    unittest.main()
