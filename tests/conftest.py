import pytest


@pytest.fixture()
def local_delapan(tmp_path, monkeypatch):
    """Hermetic delapan: tmp SQLite DB + deterministic fake embeddings."""
    monkeypatch.setenv("DELAPAN_DB_PATH", str(tmp_path / "delapan.db"))
    monkeypatch.setenv("DELAPAN_BACKEND", "local")

    async def fake_embed_batch(texts):
        return [[hash(t) % 7 * 0.1 + 0.1] * 8 for t in texts]

    async def fake_embed_text(text):
        return (await fake_embed_batch([text]))[0]

    import delapan.core.memory.persist as persist_mod
    import delapan.core.agent.preamble as preamble_mod
    monkeypatch.setattr(persist_mod, "embed_batch", fake_embed_batch)
    monkeypatch.setattr(preamble_mod, "embed_text", fake_embed_text)
    yield
