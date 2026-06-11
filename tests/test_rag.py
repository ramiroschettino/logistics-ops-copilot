from app.rag import get_index


def test_index_builds_chunks():
    index = get_index()
    assert len(index.chunks) >= 15  # 5 docs x varias secciones


def test_search_finds_argentina_customs():
    results = get_index().search("limite de valor courier argentina", k=3)
    assert results
    assert any(r["source"] == "aduanas_argentina.md" for r in results)


def test_search_handles_accents():
    """'México' y 'mexico' deben devolver lo mismo (normalizacion)."""
    a = get_index().search("impuestos en México", k=2)
    b = get_index().search("impuestos en mexico", k=2)
    assert [r["title"] for r in a] == [r["title"] for r in b]


def test_search_returns_sources():
    results = get_index().search("indemnizacion envio extraviado", k=2)
    assert results
    assert all("source" in r and "text" in r for r in results)
