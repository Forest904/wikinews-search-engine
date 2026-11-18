from bs4 import BeautifulSoup

from wikinews_ir.reader import web_url, wikimedia_image_url


def credit(info):
    fields = info.get("extmetadata")
    if not isinstance(fields, dict):
        return None

    def plain(k):
        field = fields.get(k)
        if not isinstance(field, dict) or not isinstance(field.get("value"), str):
            return ""
        value = field["value"].strip()
        if "<" in value or "&" in value:
            return BeautifulSoup(value, "html.parser").get_text(" ", strip=True)
        return value

    artist = plain("Attribution") or plain("Artist")
    license_name = plain("LicenseShortName")
    license_url = web_url(plain("LicenseUrl"))
    free = license_name.lower() in {"public domain", "cc0"} or (
        license_url.startswith(
            (
                "https://creativecommons.org/licenses/by/",
                "https://creativecommons.org/licenses/by-sa/",
                "https://creativecommons.org/publicdomain/",
            )
        )
    )
    url = wikimedia_image_url(info.get("thumburl"))
    source = web_url(info.get("descriptionurl"))
    if not (
        free
        and license_name
        and source
        and url
        and (artist or license_name.lower() in {"public domain", "cc0"})
    ):
        return None
    width, height = info.get("thumbwidth"), info.get("thumbheight")
    if not all(type(size) is int and size > 0 for size in (width, height)):
        return None
    return dict(
        url=url,
        width=width,
        height=height,
        artist=artist,
        license=license_name,
        license_url=license_url,
        source=source,
    )


def fetch_images(api, names, width, deadline=None):
    data = api.query(
        dict(
            action="query",
            format="json",
            formatversion=2,
            prop="imageinfo",
            iiprop="url|extmetadata",
            iiextmetadatafilter="Attribution|Artist|LicenseShortName|LicenseUrl",
            iiurlwidth=width,
            redirects=1,
            maxlag=5,
            titles="|".join("File:" + n for n in names),
        ),
        deadline=deadline,
    )
    query = data["query"]
    aliases = {
        r["from"]: r["to"] for group in ("normalized", "redirects") for r in query.get(group, [])
    }
    pages = {p["title"]: p for p in query["pages"]}
    result = {}
    for name in names:
        title = "File:" + name
        seen = set()
        while title in aliases and title not in seen:
            seen.add(title)
            title = aliases[title]
        infos = pages.get(title, {}).get("imageinfo", [])
        result[name] = credit(infos[0]) if infos else None
    return result
