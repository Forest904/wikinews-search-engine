"""Exclusive editorial folders for the public archive (taxonomy v1)."""

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date

MONTH_NAMES = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()


def italian_date(value):
    day = date.fromisoformat(value)
    return f"{day.day} {MONTH_NAMES[day.month - 1]} {day.year}"


def temporal_selection(catalog, current, folder, excluded):
    """Use one publication window, then diversify equally close headlines."""
    if not current[0]:
        return None
    origin = date.fromisoformat(current[0])
    groups = [[], [], []]
    for node in catalog.values():
        for row in node.articles:
            stamp, _, document_id = row
            if not stamp or document_id in excluded or document_id == current[2]:
                continue
            day = date.fromisoformat(stamp)
            distance = abs((day - origin).days)
            if distance <= 3:
                group = 0 if distance == 0 else 1
            elif day.year == origin.year:
                group = 2
                distance = abs(day.month - origin.month)
            else:
                continue
            groups[group].append((distance, day.month, node.path.split("/")[0], row))

    topic = folder.path.split("/")[0]
    for group, candidates in enumerate(groups):
        if not candidates:
            continue
        selected = []
        topics = {}
        months = set()
        while candidates and len(selected) < 3:
            _, month, branch, row = min(candidates, key=lambda c: (
                group == 2 and c[1] in months, c[0], c[2] == topic,
                topics.get(c[2], 0), c[3][2],
            ))
            selected.append(row)
            months.add(month)
            topics[branch] = topics.get(branch, 0) + 1
            candidates = [c for c in candidates if c[3][2] != row[2]]
        return {"label": ("Intanto, quel giorno…", "In quei giorni…", "Nello stesso anno…")[group],
                "date": current[0], "articles": selected}
    return None

# A deeper match wins. Within one level, declaration order is editorial priority.
BRANCHES = [
    ("Politica", "Politica e conflitti|Politica", [
        ("Elezioni", "Elezioni", [("Presidenziali", "Elezioni presidenziali", [])]),
        ("Conflitti", "Conflitti", [("Guerre", "Guerre", []), ("Attentati", "Attentati", [])]),
    ]),
    ("Tecnologia", "Scienza e tecnologia", [
        ("Informatica", "Informatica", [("Internet", "Internet", []), ("Wikimedia", "Wikimedia", [])]),
        ("Spazio", "Astronautica|Astronomia", []),
    ]),
    ("Economia", "Economia|Economia e finanza", [("Finanza", "Finanza", []), ("Lavoro", "Lavoro", [])]),
    ("Sport", "Sport", [
        ("Calcio", "Calcio|Calcio italiano", [
            ("Serie A", "Serie A (calcio)", []), ("Serie B", "Serie B (calcio)", []),
            ("Serie C1", "Serie C1 (calcio)", []), ("Serie C2", "Serie C2 (calcio)", []),
            ("Mondiali", "Campionato mondiale (calcio)", []), ("Calcio scozzese", "Calcio scozzese", []),
        ]),
        ("Ciclismo", "Ciclismo", [("Giro d’Italia", "Giro d'Italia", [])]),
        ("Rugby", "Rugby", [("Serie B", "Serie B (rugby)", [])]),
        ("Automobilismo", "Automobilismo", [("Formula 1", "Formula 1", [])]),
        *((name, name, []) for name in ("Pallacanestro", "Pallanuoto", "Ippica", "Pallavolo", "Tennis")),
    ]),
    ("Cultura e società", "Cultura e società|Società", [
        *((name, name, []) for name in ("Musica", "Cinema", "Televisione", "Religione", "Letteratura", "Istruzione")),
        ("Giochi a premi", "Giochi a premi", [("Lotto", "Lotto", []), ("Superenalotto", "Superenalotto", [])]),
    ]),
    ("Cronaca", "Giustizia e criminalità|Disastri e incidenti", [
        ("Giustizia", "Giustizia", [("Processi", "Processi", [])]),
        ("Criminalità", "Criminalità", [("Omicidi", "Omicidi", [])]),
        ("Incidenti", "Incidenti", [("Aerei", "Incidenti aerei", []), ("Stradali", "Incidenti stradali", [])]),
        *((name, name, []) for name in ("Terremoti", "Incendi", "Salute", "Ambiente", "Trasporti")),
    ]),
]


def slug(label):
    ascii_text = unicodedata.normalize("NFKD", label).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")


def rules(branches, parents=()):
    for label, aliases, children in branches:
        path = (*parents, label)
        yield path, set(aliases.split("|")), bool(children)
        yield from rules(children, path)


RULES = sorted(rules(BRANCHES), key=lambda rule: -len(rule[0]))


def classify(categories):
    names = {c.removeprefix("Categoria:") for c in categories}
    # Season categories, e.g. Serie A 2012-2013 (calcio), inherit their league.
    seasons = {}
    for name in sorted(names):
        match = re.fullmatch(r"(.+) (\d{4}-\d{4}) (\(.+\))", name)
        if match:
            seasons.setdefault(f"{match[1]} {match[3]}", match[2])
    names.update(seasons)
    for path, aliases, has_children in RULES:
        if aliases & names:
            for league in sorted(aliases & seasons.keys()):
                return (*path, seasons[league])
            return (*path, f"Altre notizie di {path[-1].lower()}") if has_children else path
    return ("Altri argomenti",)


@dataclass
class Folder:
    label: str
    path: str
    count: int = 0
    children: dict = field(default_factory=dict)
    articles: list = field(default_factory=list)

    @property
    def url(self):
        return "/archivio" + ("/" + self.path if self.path else "")


def build_catalog(rows):
    root = Folder("Archivio", "")
    folders = {"": root}
    for row in rows:
        node = root
        node.count += 1
        for label in classify(row.get("categories", [])):
            key = slug(label)
            if key not in node.children:
                path = "/".join(filter(None, (node.path, key)))
                node.children[key] = folders[path] = Folder(label, path)
            node = node.children[key]
            node.count += 1
        node.articles.append((row.get("publication_date") or "", row["title"], row["document_id"]))
    for node in list(folders.values()):
        if node.children and node.articles:
            path = node.path + "/altre-notizie"
            other = Folder("Altre notizie di " + node.label, path, len(node.articles),
                           articles=node.articles)
            node.children["altre-notizie"] = folders[path] = other
            node.articles = []
    for node in folders.values():
        node.articles.sort(key=lambda item: (item[0], item[2]), reverse=True)
        node.children = dict(sorted(node.children.items(), key=lambda pair: (pair[0].startswith("altr"), pair[0])))
    return folders
