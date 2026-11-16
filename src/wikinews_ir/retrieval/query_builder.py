"""Explicit DSL for independent, versioned retrieval experiments."""

from wikinews_ir.retrieval.profiles import profile_config


def parse_phrases(query: str) -> tuple[str, list[str]]:
    outside, phrases, current = [], [], []
    closing = None
    for char in query:
        if closing:
            if char == closing:
                phrase = "".join(current).strip()
                if not phrase:
                    raise ValueError("La frase tra virgolette non può essere vuota")
                phrases.append(phrase)
                current = []
                closing = None
                outside.append(" ")
            elif char in '"“”':
                raise ValueError("Virgolette annidate o non corrispondenti")
            else:
                current.append(char)
        elif char in '"“':
            closing = '”' if char == '“' else '"'
            outside.append(" ")
        elif char == '”':
            raise ValueError("Virgolette non corrispondenti")
        else:
            outside.append(char)
    if closing:
        raise ValueError("Chiudere le virgolette della frase")
    return " ".join("".join(outside).split()), phrases


def build_query(query: str, profile: str = "E0") -> dict:
    config = profile_config(profile)
    query = query.strip()
    if not query:
        raise ValueError("La query non può essere vuota")
    fields = config["fields"] if profile in {"E0", "E1"} else [
        f"title^{config['title_boost']:g}", "body",
    ]

    def lexical(text):
        return {"multi_match": {"query": text, "fields": fields,
                                "type": "best_fields", "operator": "or"}}

    def phrase(text):
        return {"multi_match": {"query": text, "fields": fields, "type": "phrase",
                                "slop": config["slop"], "boost": config["phrase_boost"],
                                "zero_terms_query": "none"}}

    base = lexical(query)
    if profile == "E3":
        fuzzy = lexical(query)
        fuzzy["multi_match"].update({key: config[key] for key in (
            "fuzziness", "prefix_length", "max_expansions", "fuzzy_transpositions",
        )})
        fuzzy["multi_match"]["boost"] = config["fuzzy_boost"]
        return {"bool": {"should": [base, fuzzy], "minimum_should_match": 1}}
    if profile == "E4":
        outside, phrases = parse_phrases(query)
        if phrases:
            must = [phrase(text) for text in phrases]
            if outside:
                must.append(lexical(outside))
            return {"bool": {"must": must}}
        return {"bool": {"must": [base], "should": [phrase(query)]}}
    return base
