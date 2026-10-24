"""Publish locale sitemaps expected by Material's native language navigation."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree

from markdown.extensions.toc import slugify_unicode
from mkdocs.config.defaults import MkDocsConfig
from mkdocs.plugins import event_priority

SITEMAP_NAMESPACE = "http://www.sitemaps.org/schemas/sitemap/0.9"


@event_priority(100)
def on_config(config: MkDocsConfig) -> MkDocsConfig:
    # Native Cyrillic/CJK headings need Unicode slugs. ASCII-only slugs can
    # collapse unrelated translated headings onto an English compatibility id.
    config.mdx_configs.setdefault("toc", {})["slugify"] = slugify_unicode
    return config


@event_priority(-110)
def on_post_build(config: MkDocsConfig) -> None:
    # static-i18n recursively builds all locales at priority -100. Wait until
    # its outer build has merged the complete root sitemap.
    i18n = config.plugins.get("i18n")
    if i18n is None or getattr(i18n, "building", False):
        return
    site = Path(config.site_dir)
    source = ElementTree.parse(site / "sitemap.xml")
    base_url = config.site_url.rstrip("/") + "/"
    ElementTree.register_namespace("", SITEMAP_NAMESPACE)
    for locale in ("ru", "zh"):
        document = deepcopy(source.getroot())
        for entry in list(document):
            location = entry.find(f"{{{SITEMAP_NAMESPACE}}}loc")
            if location is None or not (location.text or "").startswith(base_url + locale + "/"):
                document.remove(entry)
        target = site / locale / "sitemap.xml"
        target.parent.mkdir(parents=True, exist_ok=True)
        ElementTree.ElementTree(document).write(target, encoding="utf-8", xml_declaration=True)
