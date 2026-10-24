#!/usr/bin/env python3
"""Validate localized documentation sources and the built GitHub Pages artifact."""
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from xml.etree import ElementTree

import yaml

LOCALES = ("en", "ru", "zh")
READMES = ("README.md", "README.ru.md", "README.zh-CN.md")
LANGUAGE_NAMES = {"en": "English", "ru": "Русский", "zh": "简体中文"}


class Page(HTMLParser):
    def __init__(self, path: Path) -> None:
        super().__init__()
        self.language = ""
        self.alternates: dict[str, str] = {}
        self.ids: set[str] = set()
        self.duplicate_ids: set[str] = set()
        self.feed(path.read_text(encoding="utf-8"))

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "html":
            self.language = values.get("lang") or ""
        if values.get("id"):
            identifier = str(values["id"])
            if identifier in self.ids:
                self.duplicate_ids.add(identifier)
            self.ids.add(identifier)
        if tag == "a" and values.get("hreflang"):
            self.alternates[str(values["hreflang"])] = values.get("href") or ""


def page_url(locale: str, relative: Path) -> str:
    prefix = "" if locale == "en" else locale + "/"
    name = relative.with_suffix("").as_posix()
    if name == "index":
        return prefix
    if name.endswith("/index"):
        return prefix + name.removesuffix("index")
    return prefix + name + "/"


def code_blocks(text: str) -> list[str]:
    """Keep executable examples identical, allowing translated standalone comments."""
    blocks: list[str] = []
    current: list[str] | None = None
    fence = ""
    for line in text.splitlines():
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            if current is None:
                current, fence = [], match[1][0]
            elif match[1][0] == fence:
                blocks.append("\n".join(current))
                current = None
            continue
        if current is not None and not re.match(r"^\s*(?:#|//)", line):
            current.append(line.rstrip())
    return blocks


def check_sources(root: Path) -> list[Path]:
    docs = root / "docs"
    misplaced = sorted(p.name for p in docs.glob("*.md"))
    assert not misplaced, f"Pages must live in docs/en, docs/ru or docs/zh: {misplaced}"
    pages = sorted(p.relative_to(docs / "en") for p in (docs / "en").rglob("*.md"))
    assert pages and Path("index.md") in pages, "English documentation is missing"
    config = yaml.safe_load((root / "mkdocs.yml").read_text(encoding="utf-8"))
    i18n = next(plugin["i18n"] for plugin in config["plugins"] if isinstance(plugin, dict)
                and "i18n" in plugin)
    assert i18n["docs_structure"] == "folder", "Use a folder for each documentation language"
    assert i18n.get("reconfigure_material", True), "Enable the Material language selector"
    enabled = {item["locale"] for item in i18n["languages"] if item.get("build")}
    assert enabled == set(LOCALES), f"Expected all three enabled locales, got {enabled}"
    for locale, readme in zip(LOCALES, READMES, strict=True):
        folder = docs / locale
        translated = {p.relative_to(folder) for p in folder.rglob("*.md")}
        assert translated == set(pages), (
            f"{locale}: missing={sorted(set(pages) - translated)}, "
            f"extra={sorted(translated - set(pages))}"
        )
        text = (root / readme).read_text(encoding="utf-8")
        for language_file in READMES:
            assert f"]({language_file})" in text, f"{readme}: missing link to {language_file}"
        assert f"docs/{locale}/" in text, f"{readme}: documentation links use the wrong locale"
        for relative in pages:
            content = (folder / relative).read_text(encoding="utf-8")
            assert content.strip(), f"{locale}/{relative}: empty translation"
            anchors = re.findall(r'<a\s+id=["\']([^"\']+)["\']', content)
            assert len(anchors) == len(set(anchors)), (
                f"{locale}/{relative}: duplicate explicit section anchors"
            )
            if locale in ("ru", "zh"):
                pattern = r"[А-Яа-яЁё]" if locale == "ru" else r"[\u4e00-\u9fff]"
                assert len(re.findall(pattern, content)) >= 40, (
                    f"{locale}/{relative}: expected translated prose, not an English copy"
                )
            assert "\x01" not in content and "\x02" not in content, (
                f"{locale}/{relative}: unfinished translation markers"
            )
            assert not re.search(r"\{\s*\d+\s*\}", content), (
                f"{locale}/{relative}: unresolved translation placeholder"
            )
            if locale != "en":
                original = (docs / "en" / relative).read_text(encoding="utf-8")
                assert code_blocks(original) == code_blocks(content), (
                    f"{locale}/{relative}: executable examples differ from English"
                )
    print(f"Sources: {len(pages)} pages × 3 languages; 3 README files; code examples match")
    return pages


def check_site(root: Path, site: Path, pages: list[Path]) -> None:
    config = yaml.safe_load((root / "mkdocs.yml").read_text(encoding="utf-8"))
    base_url = config["site_url"].rstrip("/") + "/"
    for locale in LOCALES:
        for relative in pages:
            address = urljoin(base_url, page_url(locale, relative))
            destination = site / page_url(locale, relative) / "index.html"
            assert destination.is_file(), f"Missing built page: {destination}"
            page = Page(destination)
            assert page.language == locale, f"{destination}: lang={page.language!r}"
            assert not page.duplicate_ids, (
                f"{destination}: duplicate HTML ids: {sorted(page.duplicate_ids)}"
            )
            assert set(page.alternates) == set(LOCALES), (
                f"{destination}: incomplete language selector {page.alternates}"
            )
            for alternate in LOCALES:
                expected = urljoin(base_url, page_url(alternate, relative))
                actual = urljoin(address, page.alternates[alternate])
                assert unquote(actual) == unquote(expected), (
                    f"{destination}: {alternate} selector goes to {actual}, expected {expected}"
                )
    for locale in ("ru", "zh"):
        sitemap = ElementTree.parse(site / locale / "sitemap.xml")
        locations = {item.text for item in sitemap.iter(
            "{http://www.sitemaps.org/schemas/sitemap/0.9}loc"
        )}
        expected = {urljoin(base_url, page_url(locale, relative)) for relative in pages}
        assert locations == expected, f"{locale}: sitemap does not match localized pages"
    index_path = site / "search/search_index.json"
    assert index_path.is_file(), "Missing multilingual search index"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    indexed = {urlsplit(item["location"]).path for item in index["docs"]}
    for locale in LOCALES:
        for relative in pages:
            expected_path = page_url(locale, relative)
            assert expected_path in indexed or expected_path.rstrip("/") in indexed, (
                f"Search index is missing {locale}/{relative}"
            )
    print(f"Site: {len(pages) * 3} pages; same-page language selectors; multilingual search")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--site-dir", type=Path)
    args = parser.parse_args()
    try:
        pages = check_sources(args.root)
        if args.site_dir:
            check_site(args.root, args.site_dir, pages)
    except (AssertionError, FileNotFoundError, KeyError, ValueError) as exc:
        parser.exit(1, f"Documentation check failed: {exc}\n")


if __name__ == "__main__":
    main()
