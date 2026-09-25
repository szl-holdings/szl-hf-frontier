---
title: Receipt Chain Live
emoji: 🔗
colorFrom: green
colorTo: gray
sdk: static
app_file: index.html
pinned: false
license: apache-2.0
short_description: "SHA3-256 Khipu receipt chain, re-verified in your browser"
---

# receipt-chain-live

**Live SHA3-256 Khipu hash-chain verifier — re-checked IN YOUR BROWSER, not merely claimed by a server.**

A static, self-contained HTML page (0 runtime CDN) that fetches the **live a11oy receipt lake**
and **recomputes every receipt's `chain_hash` locally**, then confirms each `prev_hash` links to
the previous `chain_hash`. Green means the governance receipt chain is intact *as measured on your
own machine*.

- **Try it:** [live verifier](https://huggingface.co/spaces/SZLHOLDINGS/receipt-chain-live)
- **Source of truth:** [`szl-holdings/receipt-chain-live`](https://github.com/szl-holdings/receipt-chain-live)
- **Runtime status:** the static verifier is deployed; the upstream receipt lake is a separate
  dependency. If that service is unreachable, the verifier reports **UNAVAILABLE**, never green.

## Start here

Open the live verifier and select an organ. No account, token, wallet, or upload is required. For
local inspection, serve this repository as static files and open the printed URL:

```bash
python -m http.server 8000
```

## What it measures

The ledger ([`szl_lake_store.py`](https://github.com/szl-holdings/a11oy/blob/main/szl_lake_store.py))
commits, per organ, a hash chain where

```
chain_hash = SHA3-256( canonical_json({prev_hash, receipt_id, organ, ts, chain_index}) )
canonical_json = json.dumps(sort_keys=True, separators=(",",":"), ensure_ascii=True)
```

Every field needed for that recomputation is exposed at the receipt-envelope top level, so the
browser reproduces the exact bytes and hash with a **pinned, vendored `js-sha3` 0.8.0** (WebCrypto
has no SHA-3). The page checks, per receipt:

| Check | Label |
|---|---|
| `SHA3-256(canonical{…}) == chain_hash` | **MEASURED** — recomputed in your browser |
| `prev_hash == previous receipt's chain_hash` (chain linkage) | **MEASURED** |
| recomputed head == the lake's reported `chain_head` | **MEASURED** |
| DSSE ECDSA-P256 signatures | **REPORTED** — *not* re-verified here (see below) |
| energy (`{"label":"UNAVAILABLE"}`) | **REPORTED** pass-through — never fabricated |

## Verification boundary

| This surface verifies | This surface does **not** verify |
|---|---|
| Receipt bytes match each published `chain_hash` | DSSE signatures or signer identity |
| Adjacent `prev_hash` links are internally consistent | Receipt completeness or omission |
| The recomputed head matches the lake's reported head | Truth of the underlying decision |
| The public lake was reachable from this browser | Availability from other networks or times |

For signature and identity verification, use the end-to-end cookbook recipe
[“Verify a receipt end-to-end”](https://github.com/szl-holdings/a11oy/blob/main/docs/cookbook/recipes/01-verify-a-receipt-end-to-end.md)
with the organization [`cosign.pub`](https://github.com/szl-holdings/.github/blob/main/cosign.pub).
The Khipu chain is **Conjecture 2 (advisory BFT), not a proven theorem**; **Λ = Conjecture 1**
(advisory, never proven, trust ceiling 0.97). Energy remains null without a real meter reading.

## Provenance and freshness

- **Canonical UI source:** this GitHub repository. Review the commit SHA before reproducing a result.
- **Runtime data:** the public a11oy `/api/lake/v1` response observed by the browser at request time.
- **Computation:** local JavaScript using vendored `js-sha3` 0.8.0; no runtime CDN.
- **Privacy:** the page sends no receipt data or user input back to this repository. Normal requests
  still disclose network metadata to the Space host and upstream lake.
- **Reproducibility:** record the Git commit, receipt-lake response, organ, and observation time.

## Publication

The Hugging Face deployment is a **static** Space. Changes are authored and reviewed here, then
mirrored to the Space. A GitHub commit does not by itself prove that the live Space has updated;
verify the deployed revision before citing a live result.

## Estate

Part of the SZL Holdings estate: [a-11-oy.com](https://a-11-oy.com) ·
[a11oy (flagship + lake)](https://github.com/szl-holdings/a11oy) ·
[szl-lake](https://github.com/szl-holdings/szl-lake) ·
[🤗 SZLHOLDINGS](https://huggingface.co/SZLHOLDINGS) · Λ = Conjecture 1.

## License

[Apache-2.0](LICENSE) — consistent with the SZL Holdings estate convention (a11oy, killinchu,
anatomy, energy-attest-holo are all Apache-2.0).

## Citation

```bibtex
@software{szl_receipt_chain_live,
  title  = {receipt-chain-live: in-browser Khipu hash-chain verifier},
  author = {{SZL Holdings}},
  url    = {https://github.com/szl-holdings/receipt-chain-live},
  note   = {Cite the exact Git commit and observation time used}
}
```
