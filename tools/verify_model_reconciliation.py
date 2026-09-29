#!/usr/bin/env python3
"""Verify retained model reconciliation identity and evidence, without promotion."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import quote


def _read(root: Path, binding: dict) -> object:
    path = binding.get('path')
    if not isinstance(path, str) or not path or Path(path).is_absolute() or ':' in path or '\\' in path:
        raise ValueError('EVIDENCE_PATH_UNSAFE')
    target = (root / path).resolve()
    if not target.is_relative_to(root.resolve()) or not target.is_file():
        raise ValueError('EVIDENCE_PATH_UNAVAILABLE')
    body = target.read_bytes()
    if hashlib.sha256(body).hexdigest() != binding.get('sha256'):
        raise ValueError('EVIDENCE_DIGEST_MISMATCH')
    if 'bytes' in binding and binding['bytes'] != len(body):
        raise ValueError('EVIDENCE_LENGTH_MISMATCH')
    return json.loads(body) if target.suffix == '.json' else body


def validate(root: Path, document: dict) -> list[str]:
    errors: list[str] = []
    def require(ok: bool, code: str) -> None:
        if not ok:
            errors.append(code)
    try:
        require(document['schema'] == 'szl.estate-model-decisions/v1', 'SCHEMA')
        require(document['signature_status'] == 'UNSIGNED_OBSERVATION', 'SIGNATURE_OVERCLAIM')
        snapshots = _read(root, document['snapshot_binding'])
        expected = {'huggingface-model/' + row['path'].lower(): row for row in snapshots}
        require(bool(expected) and len(expected) == len(snapshots), 'CENSUS_CARDINALITY')
        require(all(row.get('private') is False for row in snapshots), 'NONPUBLIC_SNAPSHOT')
        inputs = {name: _read(root, binding) for name, binding in document['input_bindings'].items()}
        provider = {row['repository']: row for row in inputs['provider_sizes.json']['models']}
        require(len(inputs['provider_sizes.json']['models']) == len(expected), 'PROVIDER_CARDINALITY')
        require(set(provider) == {row['path'] for row in snapshots}, 'PROVIDER_CENSUS')
        verified = {}
        for name in ('small_artifact_bytes.json', 'adapter_artifact_bytes.json'):
            for row in inputs[name]['files']:
                require(row['repository'] in provider and row['revision'] == provider.get(row['repository'], {}).get('revision'), 'DOWNLOAD_PUBLIC_CENSUS')
                if row['provider_byte_identity_verified']:
                    verified[(row['repository'], row['revision'], row['path'])] = row
        witness = inputs['nano-and-space-witness.json']
        nanos = {row['repository']: row for row in witness['nanos']}
        require(len(nanos) == 4 and len(witness['nanos']) == 4, 'NANO_WITNESS_CARDINALITY')
        deployment = inputs['hf-deployment-receipt.json']
        require(witness['source_revision'] == deployment['source_commit'], 'RUNTIME_SOURCE_BINDING')
        require(hashlib.sha256((root / document['input_bindings']['hf-deployment-provenance.json']['path']).read_bytes()).hexdigest() == deployment['manifest_sha256'], 'PUBLICATION_MANIFEST_BINDING')
        for probe in witness['runtime'][:2]:
            body = probe['body']
            require(probe['status_code'] == 200 and body['state'] == 'SOURCE_BOUND_DEPLOYMENT', 'RUNTIME_SOURCE_STATE')
            require(body['source']['commit'] == deployment['source_commit'], 'RUNTIME_SOURCE_COMMIT')
            require(all(body['deployment'][k] == deployment[k] for k in ('hf_repository', 'hf_revision', 'manifest_sha256')), 'RUNTIME_PUBLICATION_BINDING')
        expected_decisions = ['ALLOW', 'BLOCKED', 'ESCALATE']
        require(len(witness['runtime']) == 6, 'RUNTIME_WITNESS_CARDINALITY')
        require([p['body'].get('decision') for p in witness['runtime'][3:]] == expected_decisions and all(p['status_code'] == 200 for p in witness['runtime']), 'RUNTIME_BEHAVIOR_WITNESS')
        decisions = document['decisions']
        require(len(decisions) == len(expected), 'DECISION_CARDINALITY')
        require(len({row['id'] for row in decisions}) == len(decisions), 'DUPLICATE_IDENTITY')
        require({row['id'] for row in decisions} == set(expected), 'DECISION_CENSUS')
        for row in decisions:
            identity = row['id']
            captured = expected.get(identity)
            if captured is None:
                continue
            require(row['repository'] == captured['path'], 'IDENTITY_MISMATCH:' + identity)
            require(row['observed_revision'] == captured['sha'], 'REVISION_MISMATCH:' + identity)
            require(provider[row['repository']]['revision'] == captured['sha'], 'PROVIDER_REVISION:' + identity)
            require(row['production_qualified'] is False, 'PROMOTION_FORBIDDEN:' + identity)
            require(row['training_reproduced'] is False and row['independent_evaluation_verified'] is False, 'QUALIFICATION_OVERCLAIM:' + identity)
            require(row['classification_status'] == 'RESOLVED_FOR_OBSERVED_REVISION', 'CLASSIFICATION_SCOPE:' + identity)
            require(bool(row['artifact_kind']) and bool(row['evidence']), 'CLASSIFICATION_EVIDENCE:' + identity)
            cards = [binding for binding in row['evidence'] if binding.get('kind') == 'source_card']
            require(len(cards) == 1, 'SOURCE_CARD_CARDINALITY:' + identity)
            for binding in row['evidence']:
                body = _read(root, binding)
                if binding.get('kind') == 'source_card':
                    require(binding.get('revision') == row['observed_revision'], 'SOURCE_CARD_REVISION:' + identity)
                    require(binding.get('source_path') == 'README.md', 'SOURCE_CARD_PATH:' + identity)
                    expected_url = ('https://huggingface.co/' + quote(row['repository'], safe='/')
                                    + '/resolve/' + row['observed_revision'] + '/README.md')
                    require(binding.get('url') == expected_url, 'SOURCE_CARD_URL:' + identity)
                    metadata = next((f for f in provider[row['repository']]['files'] if f['path'] == 'README.md'), None)
                    require(isinstance(body, bytes) and metadata is not None, 'SOURCE_CARD_PROVIDER_FILE:' + identity)
                    if isinstance(body, bytes) and metadata is not None:
                        require(metadata.get('size') == len(body), 'SOURCE_CARD_PROVIDER_SIZE:' + identity)
                        # The retained provider manifest binds file bytes as well as
                        # labels, so relabeling another model's card cannot pass.
                        if metadata.get('lfs'):
                            require(metadata['lfs'].get('sha256') == hashlib.sha256(body).hexdigest(), 'SOURCE_CARD_PROVIDER_DIGEST:' + identity)
                        else:
                            git_blob = hashlib.sha1(b'blob ' + str(len(body)).encode('ascii') + b'\0' + body).hexdigest()
                            require(metadata.get('git_blob_id') == git_blob, 'SOURCE_CARD_PROVIDER_DIGEST:' + identity)
            require(row['weight_bytes_verified'] == bool(row['verified_artifact_bytes']), 'BYTE_CLAIM:' + identity)
            for artifact in row['verified_artifact_bytes']:
                retained = verified.get((row['repository'], row['observed_revision'], artifact['path']))
                require(retained is not None and all(retained.get(k) == artifact.get(k) for k in ('sha256', 'bytes')), 'BYTE_BINDING:' + identity)
                metadata = next((f for f in provider[row['repository']]['files'] if f['path'] == artifact['path']), None)
                require(metadata is not None and metadata['size'] == artifact['bytes'], 'PROVIDER_BYTE_SIZE:' + identity)
                if metadata and metadata.get('lfs'):
                    require(metadata['lfs']['sha256'] == artifact['sha256'], 'PROVIDER_LFS_HASH:' + identity)
            if row['load_and_inference_verified']:
                nano = nanos.get(row['repository'])
                require(nano is not None and nano['provider_revision'] == row['observed_revision'] and nano['load_and_inference_verified'] is True, 'INFERENCE_BINDING:' + identity)
                if nano:
                    require(row['inference_witness'] == nano['inference'], 'INFERENCE_MUTATION:' + identity)
                    require(row['training_receipt_hash_matches'] == nano['training_receipt_hash_matches'] and row['canonical_source_blob_matches'] == nano['canonical_source_blob_matches'], 'NANO_BINDING:' + identity)
            if row['repository'] == 'SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v3':
                receipt = inputs['szl-receiptagent-qwen35-0.8b-v3/training_receipt.laptop-blackwell.json']
                adapter = next(a for a in row['verified_artifact_bytes'] if a['path'] == 'adapter_model.safetensors')
                require(row['training_receipt_adapter_sha256'] == receipt['adapterSha256'] and row['published_adapter_sha256'] == adapter['sha256'], 'TRAINING_RECEIPT_BINDING')
                require(row['training_receipt_hash_matches'] == (receipt['adapterSha256'] == adapter['sha256']), 'TRAINING_HASH_MISMATCH_HIDDEN')
        coverage = document['coverage']
        require(coverage['repositories'] == len(decisions), 'COVERAGE_COUNT')
        require(coverage['by_artifact_kind'] == dict(Counter(r['artifact_kind'] for r in decisions)), 'COVERAGE_KINDS')
        require(coverage['repositories_with_downloaded_artifact_bytes_verified'] == sum(r['weight_bytes_verified'] for r in decisions), 'COVERAGE_BYTES')
        require(coverage['local_inference_verified'] == sum(r['load_and_inference_verified'] for r in decisions), 'COVERAGE_INFERENCE')
        require(coverage['production_qualified'] == 0, 'COVERAGE_PROMOTION')
    except (OSError, ValueError, TypeError, KeyError, StopIteration) as exc:
        errors.append('EVIDENCE_INVALID:' + str(exc))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        document = json.loads((args.root / 'data/reconciliation/model_decisions.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        print('BLOCKED: ' + str(exc))
        return 1
    errors = validate(args.root, document)
    print(json.dumps({'valid': not errors, 'errors': errors, 'publication_authorized': False,
                      'scope': 'Retained evidence integrity and identity; no fresh execution or release qualification implied.'}, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
