# YARQA-ATTN

Canonical GitHub source for Hub `SZLHOLDINGS/YARQA-ATTN`.

**Owner: KERNEL.** This is a kernel, not a Fall 2026 ATELIER weight, not a pointer at the Triton trio (`szl-receipt-attn`, `szl-maskmod`, `szl-block-kv`), and not an alias of receipt-attn. a11oy-net must not list it as a fourth Flash / Flex / paged stack. Those three stay separate.

Quechua *yarqa* = irrigation canal that divides flow. Original SZL cut: **compartment / plug-flow attention**. Partition a sequence into canals (contiguous compartments), attend **within** a compartment, emit SHA3-256 receipts of the partition and of the attention output.

Distinct silhouettes:

| This kernel | Not this kernel |
|---|---|
| Contiguous canals, attend inside each | Flash tiled fused attention → `szl-receipt-attn` |
| Block-diagonal by construction | Flex `score_mod` + block-mask → `szl-maskmod` |
| No paged KV gather | Paged KV → `szl-block-kv` |
| Attention kernel | CFD plug-flow at `github.com/szl-holdings/yarqa` (metaphor only; different product) |

We do not copy Dao hopper, Sage `csrc`, vLLM paged `.cu`, cuDNN FMHA, TRT cubins, CuTeDSL, or `flex_attention.py`.

**SOFTWARE/KERNEL.** Not a trained model. No weights. Tokens/s and joules are not claimed.

Doctrine v11 LOCKED. Λ = Conjecture 1 (advisory; uniqueness OPEN; never a theorem). GitHub bytes are the artifact. Hub is the publish mirror. KERNEL binds Hub after this source lands. No Hub PUT of empty cards.

<!-- SZL-KERNEL-STATUS:import-LIVE:START -->
## Status

> **STATUS: import-LIVE** on CPU Kernel Hub `get_kernel` (kernels `0.16.1`). GPU cubins **UNAVAILABLE** this session (not ROADMAP).

| Thing | Label | Method / N / date / what-NOT |
|---|---|---|
| Kernel Hub `get_kernel` | **import-LIVE** | MEASURED 2026-08-28 3:08pm ET on kernels `0.16.1`. Package HEAD [`7e533ce`](https://huggingface.co/kernels/SZLHOLDINGS/YARQA-ATTN/commit/7e533ce702029061bc68f9f9cafe88efdd7f5f00) (`7e533ce702029061bc68f9f9cafe88efdd7f5f00`). README at MEASURE [`2871b3c`](https://huggingface.co/kernels/SZLHOLDINGS/YARQA-ATTN/commit/2871b3cbd73ee05e9f1aa010b75b190683f0ecd3). Legal name `yarqa-attn` (Python module `yarqa_attn`). Variants: `build/torch-universal` (default `get_kernel`) and `build/torch-cpu` (`backend="cpu"`). Working calls: `get_kernel("SZLHOLDINGS/YARQA-ATTN", revision="main", trust_remote_code=True)` and the same with `backend="cpu"`. `selfcheck` **ok**. `max_abs_vs_compartment_ref=3.58e-07` (full `3.5762786865234375e-07`), `path=torch_compartment`. What-NOT: no tokens/s; no joules; not a fourth Flash / Flex / paged stack. Lambda = Conjecture 1 (advisory). |
| GPU cubins | **UNAVAILABLE** | MEASURED 2026-08-28 7:01pm ET this session. Host `cursor` (Linux 6.12.94+ x86_64, Intel Xeon 8-core). `torch` `2.13.0+cu130` compiled CUDA 13.0. `torch.cuda.is_available()=false`. `nvidia-smi` UNAVAILABLE. `device_count=0`. Triton `3.7.1` present with no CUDA device. No cubin shipped. No tokens/s. No joules. CPU import-LIVE unchanged. Not a fourth Flash / Flex / paged stack. Lab stays Khipu. |

<!-- SZL-KERNEL-STATUS:import-LIVE:END -->

| | |
|---|---|
| **Python** | present (`torch-ext/yarqa_attn`) |
| **Path** | `torch_compartment` — CPU torch SDPA, with a labeled manual matmul+softmax fallback |
| **License** | Apache-2.0 |

## Load

After KERNEL binds Hub bytes:

```python
from kernels import get_kernel

attn = get_kernel(
    "SZLHOLDINGS/YARQA-ATTN",
    revision="main",
    trust_remote_code=True,
)
```

Source tree (labeled; not a Hub load; not import-LIVE):

```python
import torch
from yarqa_attn import yarqa_attn, ReceiptChain, selfcheck, canal_bounds

q = k = v = torch.randn(1, 2, 16, 32)
chain = ReceiptChain()
y = yarqa_attn(q, k, v, 4, chain=chain)
print(canal_bounds(16, 4), chain.verify(), selfcheck())
```

`selfcheck()` never fabricates a pass. It runs a small CPU check: slice-and-attend vs a naive block-diagonal full-attn-within-compartment reference, receipt tamper detect, and `n_canals > 1` actually splits.

## API

`yarqa_attn(q, k, v, n_canals, chain=None)` — `q,k,v` are `(batch, heads, seq, dim)` on **CPU**. Sequence length is split into `n_canals` contiguous canals (earlier canals receive the remainder). Each canal is independent attention. Outputs are concatenated along seq.

`ReceiptChain` — SHA3-256. One receipt for partition boundaries, one for the attention-output digest. `verify()` returns `(ok, depth, first_break)`.

`canal_bounds(seq_len, n_canals)` — exclusive end-points `[0, ..., seq_len]`.

v0 refuses CUDA tensors. That is honesty, not a missing bench.

## Correctness band (documented, not a bench)

fp32 vs naive within-compartment SDPA (block-diagonal keep-mask): **atol=1e-5, rtol=1e-5**.

## Tests

- kernel-builder: `nix run .#testshell-torch-ext-local` (sets `LOCAL_KERNELS`; `get_kernel` must hard-fail if that env is ignored)
- source tree (labeled, not a Hub load): `SZL_SOURCE_TREE_TESTS=1 PYTHONPATH=torch-ext python -m pytest tests/ -q`

## License

Apache-2.0. Copyright 2026 SZL Holdings. Owner: Stephen P. Lutar Jr. / SZL Holdings. Homepage: https://a-11-oy.com
