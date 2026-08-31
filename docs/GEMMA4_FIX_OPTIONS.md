# gemma4 Startup Fix — Decision Record and Fallback Options

Date: 2026-08-31. Status: **OPTION B ACTIVE.** This file records the decision
and keeps the non-chosen alternatives documented so they are never confused
with live configuration.

## Failure

gemma4-31b died at startup in staging (evidence/staging_evidence/20260831T164655Z/):
`AmbiguousGlobalPerLayerAttributeError: 'head_dim' is a per-layer attribute`
from `vllm/transformers_utils/model_arch_config_convertor.py:608`, exit 1, no OOM.
The three Qwen models passed the same staging run (smokes OK; peaks
75013/75471/73819 MiB on an 81087 MiB card).

Root cause (upstream-verified): the pinned vLLM v0.27.1 image ships
transformers >= 5.15, which guards per-layer attributes like `head_dim`;
vLLM 0.27.1's config converter still reads the global attribute → crash.
Gemma4 genuinely has two head dims (256 sliding-window / 512 global), so it is
the only pilot model affected. Upstream: vllm issue #51744 (identical traceback;
transformers==5.14.1 downgrade resolves, incl. server-up + 32-concurrent load)
and #52768 ("v0.27.1 raises; does not happen on v0.26.0").

## ACTIVE — Option B (chosen 2026-08-31)

Pin `transformers==5.14.1` inside the container at startup, gemma4's launcher
only (`serving/serve_gemma4_31b.sh`); other three models keep the frozen image.
- Pros: documented exact-symptom fix (#51744); keeps the vLLM engine binary
  identical to the other models' (best available stack uniformity); no new image.
- Risks: runtime pip weakens gemma4's environment freeze (mitigated by pinning
  the exact version and recording it here); transformers↔vLLM skew risk is
  cross-platform-verified (ROCm), so our CUDA-13/H100 stack is validated by the
  T2 shim battery at staging — any skew fails loudly there.

## FALLBACK — Option A (use ONLY if B fails staging)

Dedicated image `vllm/vllm-openai:gemma4-cu130` (vLLM's official Gemma4 recipe,
CUDA 13.0). To activate: pull the image, **pin it by digest** (the tag is
mutable), swap `IMAGE` in `serving/serve_gemma4_31b.sh`, drop the transformers
pin, re-run gemma4 staging.
- Pros: vendor-built for gemma4.
- Cons: forks gemma4 onto a different vLLM build (weaker stack uniformity than
  B); version content opaque until inspected.

## REJECTED at pre-screen — Option C (recorded, NOT an option)

Serve gemma4 on `vllm/vllm-openai:v0.26.0` (issue-reported unaffected). Rejected:
weakest evidence (one report, no gemma4-specific validation) AND its older base
CUDA leaves our `VLLM_ENABLE_CUDA_COMPATIBILITY=1` R570-driver bridge
unrevalidated. Not to be revived without new evidence.
