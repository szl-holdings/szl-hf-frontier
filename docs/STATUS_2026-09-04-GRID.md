# Status addendum — THE GRID

Date: 2026-09-04T22:55Z

## Lane

L4 exhibit. Not a model SKU. Not a kernel. Not Λ. `winner=null`.

## Surfaces

| Surface | State |
|---|---|
| github.com/szl-holdings/the-grid | LIVE source. Docs + Dockerfile. `src/game` not on GitHub yet. |
| huggingface.co/spaces/SZLHOLDINGS/the-grid | UNAVAILABLE until founder `HF_TOKEN` |
| huggingface.co/spaces/betterwithage/the-grid | UNAVAILABLE until founder `HF_TOKEN` |
| a-11-oy.com | REJECTED — product apex |
| a11oy.net | REJECTED — proof wall |

## Keys (honest)

There is no free stand-in for:

- Hugging Face write token (creates the Space)
- OpenAI key (Codex action)

Do not invent keys. Codex already fail-closes as `CODEX_UNAVAILABLE_MISSING_SECRET`.

Founder operate from a tree that contains `src/game/`:

```bash
export GITHUB_TOKEN=...
export HF_TOKEN=...
python3 scripts/payload01_align_push.py
```

Do not glow constellation until the Space serves port 7860.
