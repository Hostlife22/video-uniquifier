# Documentation languages

The documentation and repository README are available in English, Russian and
Simplified Chinese. Use the language selector in the site header to open the same
page in another language. Navigation, search controls and page contents change together.

## Source layout

```text
docs/
├── en/                 # English pages; published at the site root
├── ru/                 # Russian pages; published under /ru/
├── zh/                 # Simplified Chinese pages; published under /zh/
└── screenshots/        # Shared images
README.md               # English repository introduction
README.ru.md            # Russian repository introduction
README.zh-CN.md         # Simplified Chinese repository introduction
```

Every language has the same relative page names. For example, the installation
pages are `docs/en/install.md`, `docs/ru/install.md` and `docs/zh/install.md`.
The site keeps English URLs at the root for compatibility with existing links.

The README language links work directly on GitHub. README links point to the matching
language folder; screenshots are shared and may show the application in another language.

## Editing and translating

When adding or updating a page, update its counterparts in all three folders.
Keep CLI commands, API paths, configuration keys, filenames, units and numeric limits
consistent. Translate explanations and captions rather than identifiers. Historical
release/test counts retain their original dates and describe that revision.

Use sibling links such as `[Install](install.md)` inside a language folder.
Use `../screenshots/filename.png` for shared images. Explicit English anchors on
translated headings preserve existing section links. Navigation translations are in
`mkdocs.yml`; the language selector is supplied by Material and mkdocs-static-i18n.
Shared images use the default-language asset fallback. CI checks every page in all
three languages before building, so a missing translation cannot be published as
an English fallback.

## Build and verify

Run from the repository root:

```sh
python -m pip install -e '.[docs]'
make docs-build
make docs-serve
```

`make docs-build` checks page parity and README links, builds all languages in strict
mode, and checks generated language links and search indexes. `make docs-serve` opens
the same site with live reload. The docs CI workflow runs the build on documentation,
README, configuration and tooling changes and uploads the complete multilingual site.
Tag releases deploy that artifact to GitHub Pages through the existing deployment job.

For the same desktop/mobile Chromium menu and search checks used in CI:

```sh
python -m pip install -e '.[docs,docs-test]'
python -m playwright install chromium
python tools/check_docs_browser.py --site-dir _site
```
