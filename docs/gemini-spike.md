# Gemini free-tier gateway spike (optional, Task 6)

**Outcome: skipped — no key available.**

Checked `/Users/anthonysuherli/Repositories/8star/delapan-ai/backend/.env` (the
only source this spike was authorized to read; no account creation permitted)
for a Gemini/Google key. Present keys: `DELAPAN_BACKEND`, `AI_GATEWAY_API_KEY`,
`TAVILY_API_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `DLP_MCP_USER_EMAIL`, `DLP_MCP_USER_PASSWORD`.
Nothing matching `gemini`, `google`, or `genai` (case-insensitive grep, no
hits).

Not run: swapping `AI_GATEWAY_BASE_URL` to
`https://generativelanguage.googleapis.com/v1beta/openai/` and re-running
delapan's embed path against a throwaway `DELAPAN_DB_PATH`.

Correction (review pass, task 6): the module is `delapan/store/sqlite.py`,
not `delapan/core/store/sqlite.py`. More importantly, the anticipated failure
mode above was wrong: delapan's SQLite `vec0` table is hardcoded to 1536-dim,
but `embed_text`/`embed_batch` (`delapan/core/clients/embeddings.py:49` and
`:64`) DO pass `dimensions=emb.dim` on every embeddings.create call — that
param exists precisely to pin the output width regardless of provider
default (Gemini's is 3072-dim). So a straight dimension mismatch is not the
expected failure; the swap is plausible as long as Gemini's OpenAI-compatible
endpoint honors `dimensions` for its embedding models. Whether it actually
does remains unverified — status stays skipped: no key.
