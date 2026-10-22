# Provider: Gemini API (development AI provider)

| Field | Value |
|---|---|
| Role in Provenance | Language model and embedding provider for development, behind the provider-independent `pv_llm` interface |
| Official documentation URL | https://ai.google.dev/api |
| Capability class | Hosted API, free tier for development |
| Current integration status | Client, throttle, usage ledger and `ai-check` built in checkpoint 1.4. First feature use is checkpoint 1.5 (embeddings and resume parsing) |
| Last reviewed date | 2026-10-22 |
| Next review due | Checkpoint 1.5 (first real use) and before any launch |
| Notes | Free-tier prompts may be used by the provider to improve products: only your own test data. Real users need a paid tier with no-training terms (launch gate). Model names and prices are configuration. See `docs/operations/llm-provider-gemini.md` |
