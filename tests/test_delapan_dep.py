from delapan.mcp.tenancy import resolve_tenant
from delapan.store import get_store


def test_resolve_tenant_local(local_delapan):
    ctx = resolve_tenant("datahub-memory-test", "main", create=True)
    assert ctx.org_id == "local"
    assert ctx.kb_id
    store = get_store()
    assert store is not None
