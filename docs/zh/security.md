<a id="security-policy"></a>

# 安全政策

规范的安全策略随仓库根目录一起发布，作为 [`SECURITY.md`](https://github.com/hostlife22/video-uniquifier/blob/main/SECURITY.md)，以便 GitHub 自动检测并显示
**安全 → 报告漏洞** 按钮。

<a id="release-inventory-scope-v160-preparation"></a>

## 发行库存范围（v1.6.0 准备）

`tools/bundle_sbom.py` 会清点实际的本地包/提取的 AppImage，而不是安装在无关运行环境中的软件包。四个平台特定的 CycloneDX 1.5 文档包括常规文件 SHA-256 哈希、符号链接目标以及捆绑 Python METADATA 中的软件包名称/版本。每个文档都标识了归档哈希和源提交；发行工作流验证绑定和 cosign 签名。旧版 `sbom.cdx.json` 明确作为构建环境的证据。

这使用了 CycloneDX 的 [文件/组件完整性表示](https://cyclonedx.org/guides/sbom/relationships/)。文件覆盖范围并不能建立完整的依赖图：不透明的 PYZ/静态二进制内容、外部操作系统库以及完整的许可归属仍未经过验证。Cosign 认证的是工作流来源，而不是 Apple 公证或 Windows Authenticode。在手动 Docker 资格认证时，需要使用唯一的候选标签，而不是 `latest`/`edge`，当需要进行注册表证明验证时。

<a id="reporting-a-vulnerability"></a>

## 报告漏洞

使用以下任一渠道：

1. **GitHub 私有漏洞报告** — 在仓库页面，**Security → Report a vulnerability**，或打开 [直接链接](https://github.com/hostlife22/video-uniquifier/security/advisories/new)。
2. **电子邮件** — 致 `sen.serafim.dev2gmail.com`，邮件主题前缀
   `[video-uniquifier security]`.

**请不要为疑似漏洞开启公开问题。**

<a id="response-timeline"></a>

## 响应时间表

|严重性|确认|已修复|
|---|---|---|
|**关键**|在1个工作日内|在14个日历日内|
|**高**|在3个工作日内|在30个日历日内|
|**中**|在5个工作日内|在60个日历日内|
|**低**|尽力而为|下一个次要版本发布|

<a id="supported-versions"></a>

## 支持的版本

安全修复将应用于最新的主要.次要版本系列。

|版本|安全修复|
|---|---|
|**2.2.x**|✅ 活跃|
|2.1.x 及更早版本|❌ 结束支持|

请参阅完整政策 —— 范围、披露时间表、名人堂 —— 在 [`SECURITY.md`](https://github.com/hostlife22/video-uniquifier/blob/main/SECURITY.md)。

有关 SemVer 承诺以及如何提出破坏性更改，请参阅 [版本管理](versioning.md)。
