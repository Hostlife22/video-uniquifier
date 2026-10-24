#!/usr/bin/env python3
"""Exercise the built language menu and search in desktop and mobile Chromium."""
from __future__ import annotations

import argparse
import functools
import http.server
import tempfile
import threading
from pathlib import Path

from playwright.sync_api import sync_playwright


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        pass


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site-dir", type=Path, default=Path("_site"))
    parser.add_argument("--screenshots", type=Path)
    args = parser.parse_args()
    site = args.site_dir.resolve()
    assert (site / "index.html").is_file(), "Build the documentation first"
    with tempfile.TemporaryDirectory(prefix="video-docs-browser-") as directory:
        (Path(directory) / "video-uniquifier").symlink_to(site, target_is_directory=True)
        handler = functools.partial(QuietHandler, directory=directory)
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}/video-uniquifier/"
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    scenarios = 0
                    for width, height in ((1366, 900), (390, 844)):
                        context = browser.new_context(viewport={"width": width, "height": height})
                        errors: list[object] = []
                        page = context.new_page()
                        page.on(
                            "pageerror",
                            lambda error, captured=errors: captured.append(str(error)),
                        )
                        for topic in ("", "install/", "facebook-reels/"):
                            page.goto(base + topic, wait_until="networkidle")
                            for locale in ("ru", "zh", "en"):
                                page.locator(".md-header .md-select > button").click()
                                page.locator(f'.md-select a[hreflang="{locale}"]').click()
                                prefix = "" if locale == "en" else locale + "/"
                                page.wait_for_url(base + prefix + topic)
                                assert page.locator("html").get_attribute("lang") == locale
                                assert page.locator("h1").first.inner_text().strip()
                                assert page.evaluate(
                                    "document.documentElement.scrollWidth <= window.innerWidth"
                                ), f"Horizontal overflow at {page.url}, width={width}"
                                if not topic and args.screenshots:
                                    args.screenshots.mkdir(parents=True, exist_ok=True)
                                    destination = args.screenshots / f"{locale}-{width}.png"
                                    page.screenshot(path=str(destination))
                                scenarios += 1
                                print(f"{width}px: {locale}/{topic or 'index'} passed", flush=True)
                        # Search with a local term after the search worker initializes.
                        for locale, query in (("en", "installation"), ("ru", "установка"),
                                              ("zh", "安装")):
                            prefix = "" if locale == "en" else locale + "/"
                            page.goto(base + prefix, wait_until="networkidle")
                            page.keyboard.press("/")
                            field = page.locator('[data-md-component="search-query"]')
                            field.wait_for(state="visible")
                            print(f"{width}px: searching {locale}: {query}", flush=True)
                            field.fill(query)
                            # Complete the keyboard/IME interaction observed by Material.
                            field.press("End")
                            page.locator(".md-search-result__item").first.wait_for(state="visible")
                            page.keyboard.press("Escape")
                        assert not errors, f"Browser errors: {errors}"
                        context.close()
                    print(f"Browser: {scenarios} same-page language switches; 6 localized searches")
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
