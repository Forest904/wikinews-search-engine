from wikinews_ir.archive import build_catalog, temporal_selection


def test_temporal_windows_cross_year_exclusions_and_month_diversity():
    dates = ["2020-12-31", "2020-12-31", "2021-01-03", "2021-01-04",
             "2020-12-01", "2020-12-02", "2020-11-01", "2020-10-01", ""]
    catalog = build_catalog(dict(document_id=str(i), title=str(i), publication_date=d)
                            for i, d in enumerate(dates))
    folder = catalog["altri-argomenti"]
    current = (dates[0], "0", "0")

    def ids(excluded):
        selection = temporal_selection(catalog, current, folder, excluded)
        return [row[2] for row in selection["articles"]]

    assert ids(set()) == ["1"]
    assert ids({"1"}) == ["2"]
    assert ids({"1", "2"}) == ["4", "6", "7"]
    assert temporal_selection(catalog, ("", "8", "8"), folder, set()) is None
    assert temporal_selection(catalog, current, folder, set("124567")) is None


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
