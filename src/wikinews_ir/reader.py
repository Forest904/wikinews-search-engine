"""Structured reader extraction from the archived Parsoid revision."""
import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

from lxml import html

DEFAULT_PATH = Path("data/reader/catalog.sqlite3")
TAGS = set("p br h2 h3 h4 h5 h6 strong b em i u s small sub sup blockquote ol ul li dl dt dd table caption thead tbody tfoot tr th td a cite".split())
SECTIONS = {"articoli correlati": "related", "vedi anche": "related", "fonti": "sources",
            "note": "sources", "collegamenti esterni": "sources", "altri progetti": "skip"}
OMIT = set("head script style nav footer form button iframe object embed input link meta noscript audio video".split())


def key(value):
    return " ".join(unquote(value).replace("_", " ").split())


def web_url(value, base=""):
    if not value or "\\" in value or any(ord(c) < 32 for c in value):
        return ""
    try:
        absolute = urljoin(base, value)
        parts = urlsplit(absolute)
        if parts.scheme in ("https", "http") and parts.hostname and not parts.username and not parts.password:
            return absolute
    except ValueError:
        pass
    return ""


def wikimedia_image_url(value):
    url = web_url(value, "https://it.wikinews.org")
    return url if url.startswith(("https://upload.wikimedia.org/", "https://thumb.wikimedia.org/")) else ""


def destination(href, titles, base):
    url = web_url(href, base)
    parts = urlsplit(url)
    if parts.hostname == "it.wikinews.org" and parts.path.startswith("/wiki/"):
        doc = titles.get(key(parts.path[6:]))
        if doc:
            return "/articles/" + doc
    return url


def extract(markup, base, titles):
    tree = html.document_fromstring(markup)
    related, sources, figures = [], [], []
    for el in list(tree.iterdescendants()):
        if not isinstance(el.tag, str):
            continue
        classes = set(el.get("class", "").split())
        if (el.tag in OMIT or classes & {"metadata", "noprint", "boilerplate", "navbox", "toc",
                "mw-editsection", "reference", "sisterproject", "sisterprojectbox"}
                or (el.tag in {"table", "div"} and any(name in el.get("data-mw", "").lower()
                    for name in ("./template:notizia_originale", "./template:interprogetto")))
                or el.get("id") in {"commentrequest", "condivisione-articolo"}
                or re.search(r"display\s*:\s*none", el.get("style", ""), re.I)):
            el.drop_tree()
    def add_related(a):
        href = destination(a.get("href"), titles, base)
        label = " ".join(a.text_content().split())
        if not href or not label or any(part in unquote(href).casefold() for part in (
                "/wiki/pagina_principale", "/wiki/categoria:", "/wiki/speciale:", "/wiki/file:")):
            return
        if all(x["href"] != href for x in related):
            related.append(dict(href=href, label=label))

    def children(el):
        result = [el.text] if el.text else []
        section = None
        level = 7
        for child in el:
            tag = child.tag
            if not isinstance(tag, str):
                if child.tail and not section:
                    result.append(child.tail)
                continue
            if re.fullmatch("h[1-6]", tag):
                depth = int(tag[1])
                if depth <= level:
                    section = SECTIONS.get(" ".join(child.text_content().lower().split()))
                    level = depth if section else 7
                if section:
                    continue
            if section in ("sources", "related"):
                if section == "related":
                    for a in child.xpath("self::a[@href] | .//a[@href]"):
                        add_related(a)
                else:
                    entries = child.xpath("self::cite|.//cite") or child.xpath("self::li|.//li") or [child]
                    for entry in entries:
                        label = " ".join(entry.text_content().split())
                        anchors = entry.xpath("self::a[@href]|.//a[@href and not(@class='extiw')]")
                        href = destination(anchors[0].get("href"), titles, base) if anchors else ""
                        citation = dict(label=label, href=href)
                        if label and citation not in sources:
                            sources.append(citation)
            elif not section:
                result.extend(convert(child))
                if child.tail:
                    result.append(child.tail)
        return result

    def convert(el):
        tag = el.tag
        if not isinstance(tag, str) or tag == "img":
            return []
        if tag == "figure":
            imgs = el.xpath(".//img[@resource]")
            if not imgs:
                return []
            img = imgs[0]
            name = unquote(img.get("resource")).removeprefix("./File:").replace("_", " ")
            if (not re.search(r"\.(jpe?g|png|webp)$", name, re.I)
                    or re.search(r"logo|icon|flag of|stemma|pictogram", name, re.I)
                    or not wikimedia_image_url(img.get("src"))):
                return []
            caption = " ".join(el.xpath("string(figcaption)").split())
            figure = dict(tag="figure", file=name, caption=caption, alt=img.get("alt", ""))
            figures.append(figure)
            return [figure]
        if tag == "table":
            headings = {" ".join(h.text_content().lower().split()) for h in el.xpath(".//th|./caption")}
            if headings & {"notizia originale", "ricerca originale"}:
                return []
            if headings & {"articoli correlati", "vedi anche"}:
                for a in el.xpath(".//a[@href]"):
                    add_related(a)
                return []
        inside = children(el)
        if tag not in TAGS:
            return inside
        if tag == "table" and not (el.xpath(".//th|./caption") or "wikitable" in el.classes
                                    or len(el.xpath(".//tr[td[2]]")) >= 2):
            # Unwrap layout cells while retaining their contents.
            def flatten(nodes):
                for n in nodes:
                    if isinstance(n, dict) and n["tag"] in {"tbody","tr","td","thead","tfoot"}:
                        yield from flatten(n["children"])
                        if n["tag"] == "td":
                            yield " "
                    else:
                        yield n
            return list(flatten(inside))
        attrs = {}
        if tag == "a":
            href = destination(el.get("href"), titles, base)
            if not href:
                return inside
            attrs["href"] = href
        if tag in ("td", "th"):
            for attr in ("colspan", "rowspan"):
                v = el.get(attr, "")
                if re.fullmatch(r"[1-9][0-9]{0,2}", v):
                    attrs[attr] = v
            if el.get("scope") in ("row","col","rowgroup","colgroup"):
                attrs["scope"] = el.get("scope")
        return [dict(tag=tag, attrs=attrs, children=inside)]

    blocks = children(tree.find("body") if tree.find("body") is not None else tree)
    selected = next((f for f in figures if f["caption"]), figures[0] if figures else None)
    if selected:
        selected["selected"] = True
    return dict(blocks=blocks, related=related, sources=sources, file=selected["file"] if selected else None)


def read_page(doc, revision, checksum):
    path = Path(os.getenv("READER_CATALOG", DEFAULT_PATH))
    if not path.is_file():
        return None
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
            row = db.execute("SELECT payload, media.data FROM pages JOIN manifest ON checksum=? "
                             "LEFT JOIN media ON pages.file=media.name WHERE id=? AND revision=?",
                             (checksum, doc, revision)).fetchone()
        if row and row[0]:
            return {**json.loads(row[0]), "image": json.loads(row[1]) if row[1] else None}
    except (sqlite3.Error, OSError, ValueError):
        pass
    return None
