<a id="community-profile-marketplace-f9-v090-r1"></a>

# 社区配置库

浏览并安装由社区贡献的 YAML 配置文件 —— 无需离开 CLI 或 GUI，并且无需信任任何在你的机器上执行的代码。目录根据每条目使用 SHA 固定；不匹配声明哈希的配置文件会在文件写入磁盘前被拒绝。

<a id="trust-model"></a>

## 信任模型

* **仅限 HTTPS。** 目录及其引用的每个配置文件 URL 都被强制为 `https://`。不使用 HTTPS 的 URL 无论来源如何，都将在读取任何字节之前被拒绝。
* **SHA-256 固定。** 每个目录条目都包含其指向的配置文件 YAML 的十六进制 SHA-256。`install` 会下载、计算哈希，并且如果摘要不匹配，将拒绝写入文件。
* **Ed25519 签名 (v1.2.0 任务 25)。** 目录条目可能包含一个 `signature` 字段 — 64 个原始 Ed25519 字节，十六进制编码 — 由市场运营者使用离线私钥对条目生成
  `sha256` 字段。当签名强制启用时（`install()` API 上的 `require_signature=True` 或
  `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1` 在环境中），未签名的条目以及其签名无法通过任何捆绑的市场公钥验证的条目将被拒绝。参见 § 签名策略。
* **模式验证。** 即使在 SHA 匹配之后，YAML 也会在原子重命名到每个用户的配置文件目录之前，先通过 `Profile.model_validate`（使用 `extra=forbid`）运行。格式错误的配置文件永远不会到达其最终文件名。
* **无代码执行。** 配置文件是声明式 YAML；仅加载它会调用 pydantic 模式。不存在市场条目可以在你的计算机上执行任意代码的路径。
* **不会静默失败。** 传输错误（网络中断、TLS 失败）会依次回退到本地缓存 → 内置轮子引导程序。配置形状错误（payload 过大、非 HTTPS URL、JSON 解析失败）会作为致命错误传播——我们不会因为上游配置错误而提供过时的目录。

## CLI

```bash
video-uniq profile list-community          # cached + sorted by id
video-uniq profile list-community --refresh
video-uniq profile show cid_aware          # inspect before install
video-uniq profile install cid_aware       # → ~/.config/video_uniquifier/profiles/
video-uniq profile install cid_aware --dest /custom/dir --overwrite
video-uniq profile install-dir             # print default install dir
video-uniq profile purge-cache             # force re-fetch on next call
```

## GUI

配置文件编辑器屏幕有一个 **浏览社区…** 按钮。对话框列出每个目录条目，选择时显示 URL 和 SHA，并在点击时安装到你每个用户的配置文件目录中。已安装的配置文件会在下拉列表中显示，无需重启。

<a id="catalog-format"></a>

## 目录格式

```json
{
  "version": 1,
  "entries": [
    {
      "id": "cid_aware",
      "name": "CID-aware (balanced)",
      "description": "Conservative micro-transforms…",
      "url": "https://raw.githubusercontent.com/…/cid_aware.yaml",
      "sha256": "d4cdb9e4877387ec259524da6ef9806c…",
      "author": "video-uniquifier core",
      "tags": ["cid", "balanced"],
      "version": "1.0.0",
      "min_video_uniquifier_version": "0.9.0"
    }
  ]
}
```

模式位于 `core/profile_marketplace.py::Catalog`（带有
`extra=forbid`）；验证会拒绝任何未知字段。

<a id="where-things-live"></a>

## 内容存放位置

|项目|路径|
|----------------------|------------------------------------------------------------|
|引导目录| `<wheel>/video_uniquifier/marketplace/catalog.json`           |
|缓存目录| `~/.cache/video_uniquifier/marketplace/catalog.json`          |
|已安装配置文件|`~/.config/video_uniquifier/profiles/<id>.yaml`（默认）|
|项目目录| `https://raw.githubusercontent.com/Hostlife22/video-uniquifier/main/src/video_uniquifier/marketplace/catalog.json` |

引导目录随 wheel 一起提供，因此即使在没有网络的情况下进行全新安装，仍会列出少量初始配置文件。同样的目录托管在项目仓库中；在刷新时，成功的网络获取会覆盖。

<a id="contributing-a-profile"></a>

## 贡献配置文件

1. 根据 [配置文件](profiles.md) 中记录的模式编写 YAML。运行 `video-uniq preflight <some_source> --profile <your.yaml>` 进行合理性检查。
2. 计算最终 YAML 的 SHA-256：

    ```bash
    shasum -a 256 your_profile.yaml
    ```

3. 针对 `Hostlife22/video-uniquifier` 提交一个 PR 更新
   `src/video_uniquifier/marketplace/catalog.json` 并新增一条条目。包括 `author`，一行描述
   `description`，以及至少一个 `tag`。
4. 提及 YAML 的托管 URL —— 原始 GitHub URL 是标准选择。URL **必须** 是 HTTPS。

审阅者将从你的分支安装配置文件，然后在参考源上运行它，并验证 SHA 是否匹配。

<a id="signing-policy-v120-task-25"></a>

## 签名策略（v1.2.0 任务 25）

目录条目可以由市场运营商签名。捆绑的公钥集合位于 `src/video_uniquifier/keys/marketplace.pub`（随 wheel 一起提供）——每一行非注释行包含一个十六进制编码的 Ed25519 公钥，在密钥轮换期间允许多个密钥。

<a id="what-gets-signed"></a>

### 签什么

签名覆盖条目中 `sha256` 字段的 ASCII 字节——与固定 YAML 内容的十六进制字符串相同。将签名绑定到 SHA 意味着单个签名同时验证 URL 目标和正文内容：企图将 `url` 改为不同 YAML 的攻击者也必须将 `sha256` 改以匹配，否则签名将失效，除非他们也拥有操作员的私钥。

<a id="signing-workflow"></a>

### 签名工作流程

```bash
# One-off setup: generate the operator's keypair.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
priv = ed25519.Ed25519PrivateKey.generate()
print('PRIVATE (keep offline!):',
      priv.private_bytes(serialization.Encoding.Raw,
                         serialization.PrivateFormat.Raw,
                         serialization.NoEncryption()).hex())
print('PUBLIC (ship in marketplace.pub):',
      priv.public_key().public_bytes(serialization.Encoding.Raw,
                                     serialization.PublicFormat.Raw).hex())
"

# Per-entry: sign the body SHA.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIV_HEX))
sha256_hex = '<the entry\\'s sha256 field>'
print(priv.sign(sha256_hex.encode('ascii')).hex())
"
```

将生成的 128 个字符的十六进制字符串粘贴到目录条目的
`signature` 字段。

<a id="key-rotation"></a>

### 密钥轮换

1. 生成新的密钥对。
2. 将新的公钥追加到 `marketplace.pub` 中 **旧密钥之上**。两个密钥仍然有效；验证接受针对任何已列出密钥的签名。
3. 使用新的私钥重新签署每个活跃的目录条目。
4. 所有条目重新签署完成后，移除旧的公钥从
   在下一个 video-uniquifier 版本中 `marketplace.pub`。
5. 永久销毁旧的私钥。

<a id="enforcement"></a>

### 执行

签名验证是可选的，以保持与 v0.9 目录格式的向后兼容性。希望启用仅签名模式的操作员：

* 在代码中将 `require_signature=True` 传递给 `install(...)`。
* 或在生成 `video-uniq` / `video-uniq-gui` 的 shell 中导出 `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1`。

`cryptography` 包（PyCA 参考）作为
`[crypto]` 额外组件捆绑。未安装该额外组件的安装仍然可以使用未经签名的目录；在非-`[crypto]` 安装中开启强制执行会引发一个明确的错误，指向缺失的依赖。
