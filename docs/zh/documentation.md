<a id="documentation-languages"></a>

# 文档语言

文档和仓库 README 均提供英语、俄语与简体中文。
页眉中的语言菜单会打开当前页面的其他语言版本，同时更新导航、搜索控件与正文。

<a id="source-layout"></a>

## 源码结构

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

每种语言保持相同的页面相对路径。例如，安装文档分别为 `docs/en/install.md`、
`docs/ru/install.md` 与 `docs/zh/install.md`。英语版本仍发布在站点根目录，
俄语位于 `/ru/`，简体中文位于 `/zh/`，从而保留现有英语链接。

README 中的语言链接可以直接在 GitHub 上使用，每个 README 都链接到相应语言目录。
图片共用；截图中的应用语言可能与当前文档语言不同。

<a id="editing-and-translating"></a>

## 编辑与翻译

新增或修改页面时，请同步更新三个语言目录中的对应页面。
CLI 命令、API 路径、配置键、文件名、单位与数值限制必须保持一致；
翻译说明和标题，不翻译程序标识符。历史版本的测试结果保留原日期，
其结论只适用于对应修订版本。

语言目录内部使用同级链接，例如 `[安装](install.md)`。
共用图片使用 `../screenshots/filename.png`。
译文标题前的显式英语锚点用于保留已有的章节链接。
导航译文配置在 `mkdocs.yml` 中，语言菜单由 Material 与 mkdocs-static-i18n 提供。
共用图片通过默认语言资源回退获取。CI 会在构建前检查每一页的三种语言版本，
缺失译文将导致失败，不能以英语回退页面代替译文发布。

<a id="build-and-verify"></a>

## 构建与验证

在仓库根目录运行：

```sh
python -m pip install -e '.[docs]'
make docs-build
make docs-serve
```

`make docs-build` 检查页面是否齐全、README 链接是否正确，以严格模式构建三种语言，
并验证生成页面的语言菜单和搜索索引。`make docs-serve` 提供支持自动刷新的本地预览。
文档 CI 会在文档、README、配置或验证工具发生变化时运行，并上传完整多语言站点。
发布版本标签时，现有部署任务将该产物发布到 GitHub Pages。

运行与 CI 相同的桌面和移动 Chromium 语言菜单及搜索检查：

```sh
python -m pip install -e '.[docs,docs-test]'
python -m playwright install chromium
python tools/check_docs_browser.py --site-dir _site
```
