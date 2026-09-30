---
license: apache-2.0
pretty_name: SZL Holdings — release assets (UNAVAILABLE, placeholder)
tags:
- szl-holdings
- release-assets
- placeholder
- not-a-dataset
task_categories:
- other
size_categories:
- n<1K
language:
- en
---

# SZL Holdings — release assets

> **Lifecycle: PLACEHOLDER / UNAVAILABLE. Production-ready: false.** At the
> revision that added this card, the repository contained only `.gitattributes`.
> No release asset, dataset payload, schema, checksum, or receipt has been
> published here.

This Hub ID is reserved for signed release assets (tarballs, checksums, SBOMs,
attestations) that the estate's release workflows may publish in future. Until
an asset lands with its own receipt, the honest state of this repository is
**UNAVAILABLE**: it must not be cited as evidence, downloaded as data, or
treated as a release channel.

## Where releases actually live today

| Artifact | Location |
|---|---|
| Software releases and attestations | [github.com/szl-holdings](https://github.com/szl-holdings) — per-repository Releases and `gh attestation verify` |
| Receipt store | [SZLHOLDINGS/szl-lake](https://huggingface.co/datasets/SZLHOLDINGS/szl-lake) |
| Model bill of materials | [SZLHOLDINGS/model-bom](https://huggingface.co/datasets/SZLHOLDINGS/model-bom) |
| Formal-artifact record | [10.5281/zenodo.20434276](https://doi.org/10.5281/zenodo.20434276) |

## Evidence boundary

| Subject | Evidence state | Basis |
|---|---|---|
| Repository identity | **OBSERVED** | Authenticated read on 2026-09-25 |
| Release assets | **UNAVAILABLE** | No data-bearing file exists in the repository |
| Dataset artifact license | **BLOCKED** | No artifact exists; the `apache-2.0` declaration covers repository-card materials only |
| Production-ready status | **BLOCKED** | Placeholder only |

Governed by [SZL Doctrine v11](https://github.com/szl-holdings/.github/blob/main/doctrine/DOCTRINE_V11.md): label down, never up.
