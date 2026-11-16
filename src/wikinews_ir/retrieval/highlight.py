"""Decode only our highlighting tags; never expose source HTML as markup."""

from html.parser import HTMLParser


class SegmentParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.segments = []
        self.marked = False

    def handle_starttag(self, tag, attrs):
        if tag == "mark" and not attrs:
            self.marked = True
        else:
            self.handle_data(self.get_starttag_text())

    def handle_endtag(self, tag):
        if tag == "mark":
            self.marked = False
        else:
            self.handle_data(f"</{tag}>")

    def handle_data(self, data):
        if data:
            self.segments.append({"text": data, "highlighted": self.marked})


def segments(fragments):
    if not fragments:
        return []
    parser = SegmentParser()
    parser.feed(fragments[0])
    parser.close()
    return parser.segments


HIGHLIGHT = {
    "type": "unified", "encoder": "html", "pre_tags": ["<mark>"],
    "post_tags": ["</mark>"], "max_analyzed_offset": 100000,
    "fields": {"title": {"number_of_fragments": 0},
               "body": {"number_of_fragments": 1, "fragment_size": 240}},
}
