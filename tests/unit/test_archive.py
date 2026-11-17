from wikinews_ir.archive import build_catalog


def test_exclusive_membership_seasons_fallback_and_order():
    categories = [
        ["Politica", "Calcio", "Serie A 2012-2013 (calcio)"],
        ["Serie A (calcio)"], ["Calcio"], ["Pubblicati"], ["Finanza"], ["Finanza"],
    ]
    rows = [
        dict(document_id=str(i), title=str(i), categories=cats,
             publication_date="2020-01-01" if i == 5 else None)
        for i, cats in enumerate(categories)
    ]
    catalog = build_catalog(rows)
    assert catalog[""].count == len(rows)
    assert catalog["sport/calcio/serie-a/2012-2013"].articles[0][2] == "0"
    assert catalog["sport/calcio/serie-a/altre-notizie"].count == 1
    assert catalog["altri-argomenti"].count == 1
    assert [doc[2] for doc in catalog["economia/finanza"].articles] == ["5", "4"]
    assert sorted(doc[2] for node in catalog.values() for doc in node.articles) == [
        row["document_id"] for row in rows
    ]
    for folder in catalog.values():
        if folder.children:
            assert not folder.articles
            assert folder.count == sum(child.count for child in folder.children.values())
