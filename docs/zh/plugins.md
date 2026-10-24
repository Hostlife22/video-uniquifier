<a id="transform-plugins"></a>

# 变换插件

> 在 v0.8.0 中添加。通过清单+能力门+审计钩在 v1.2.0 中加固
> 沙盒（任务 23）。

内置变换（裁剪+重缩放、颜色抖动、响度规范化、音高+节奏…）位于
`src/video_uniquifier/core/transforms/` 并在导入时通过 `register(TransformSpec(…))` 自注册。**插件**只是一个外部 Python 包，执行完全相同的操作——它提供一个调用 `register(...)` 的模块，并在 `video_uniquifier.transforms` 条目点组中宣传该模块，以便 video-uniquifier 自动发现它。

不需要分叉。对 `core/` 没有任何修改。发布到 PyPI 的插件在 `pip install` 之后对同一虚拟环境中的每个 video-uniquifier 安装都可见。

<a id="manifest-v120"></a>

## 清单 (v1.2.0)

每个第三方插件分发包必须在包根目录下提供一个 `video_uniquifier_plugin.toml` 文件。清单声明了插件允许注册的转换类型；尝试注册清单未选择的类型会在加载时引发 `PluginViolation`。

```toml
[plugin]
name = "my-uniq-pingpong"
version = "0.1.0"
capabilities = ["video_transform"]   # add "audio_transform" to register audio
# sha256 = "…"                       # optional self-declared wheel hash
```

`name` 和 `version` 是必需的。`capabilities` 是一个列表：

|功能|允许 `TransformSpec.kind`|备注|
|--------------------|------------------------------|-------|
| `video_transform`  | `"video"`                    |任何 `video.*` ID 都必须提供|
| `audio_transform`  | `"audio"`                    |任何 `audio.*` ID 都必须提供|

省略 `capabilities` 的插件仍可加载（其清单有效），但无法注册任何转换——可用作无操作探针以验证发现机制。

将清单作为包数据发布，以便 `importlib.metadata.distribution(...).files` 能够包含它。示例 `pyproject.toml` 代码片段：

```toml
[tool.setuptools.package-data]
my_uniq_pingpong = ["video_uniquifier_plugin.toml"]
```

<a id="trust-model-v120"></a>

## 信任模型 (v1.2.0)

插件是普通的 Python 包，因此加载一个插件会运行第三方的任意代码。v1.2.0 在入口点之上增加了两层纵深防御。
`try/except` 在 v0.8.0 引入：

1. **清单功能门** —— 来自没有清单的插件，或者其清单中未列出匹配功能的 `register()` 调用，会在转换到达注册表之前被拒绝。
2. **审计钩沙箱** —— 每个插件的导入时代码和它提供的每个转换构建器都在 `sys.addaudithook` 门内运行。被禁止的操作（文件系统写入 — `os.unlink`/`os.remove`/`os.rename`，网络外发 — `socket.connect`/`socket.bind`，子进程生成 —
   `subprocess.Popen`/`os.exec*`，动态 `exec`/`compile`）会抛出
   `PluginViolation` 而不是默默成功。

沙箱通过 [PEP 578 审计钩子](https://peps.python.org/pep-0578/) 实现，并且是跨平台的（CPython，无操作系统特定代码）。它会捕获通过 CPython 运行时的所有内容；如果插件包含 C 扩展并发出原始系统调用，则会绕过此层。Linux `seccomp` 是未来版本中作为更强第二层的候选。

<a id="operator-controls"></a>

### 操作员控制

|标志 / 环境变量|作用|
|---|---|
| `--no-plugins`  /  `VIDEO_UNIQ_NO_PLUGINS=1`               |跳过所有第三方插件。环境变量是在导入前完全生效；命令行标志在注册表后过滤，因此导入时的副作用已执行。|
| `--plugins-allowlist a,b`  /  `VIDEO_UNIQ_PLUGINS_ALLOWLIST=a,b` |仅保留 `[plugin].name` 在逗号分隔列表中的插件。|
| `--unsafe-plugins`                                       |禁用审计钩子沙箱。仅与受信任的内部插件一起使用；不要用于 PyPI 安装。|

在生产部署中优先使用环境变量形式：它在任何插件导入之前生效，因此恶意插件的 `__init__.py` 永远不会运行。

<a id="minimal-plugin-hello-world"></a>

## 最小插件（hello-world）

项目布局：

```
my-plugin/
├── pyproject.toml
└── src/
    └── my_uniq_pingpong/
        └── __init__.py
```

`src/my_uniq_pingpong/__init__.py` — 注册作为导入的副作用运行，就像内置插件一样：

```python
from pydantic import BaseModel, Field
from video_uniquifier.core.transforms import FilterChain, LabelAllocator, TransformSpec, register


class PingPongParams(BaseModel, extra="forbid"):
    strength: float = Field(0.0, ge=0.0, le=1.0)


def build(params: PingPongParams, alloc: LabelAllocator, in_label: str) -> FilterChain:
    out = alloc.next("v")
    # Trivial example: identity filter wrapped to demonstrate the contract.
    return FilterChain(in_label=in_label, out_label=out, filter_str="null")


register(TransformSpec(id="video.pingpong", kind="video", schema=PingPongParams, build=build))
```

`pyproject.toml` — 入口点声明是将其连接起来的方式：

```toml
[project]
name = "my-uniq-pingpong"
version = "0.1.0"
dependencies = ["video-uniquifier", "pydantic>=2"]

[project.entry-points."video_uniquifier.transforms"]
pingpong = "my_uniq_pingpong"
```

在与 video-uniquifier 相同的环境中安装：

```bash
pip install -e ./my-plugin
video-uniq probe --list-transforms | grep pingpong
# video.pingpong
```

在任何配置文件 YAML 中引用新的转换：

```yaml
transforms:
  - id: video.pingpong
    params: { strength: 0.5 }
```

<a id="contract-reminder"></a>

## 合同提醒

转换构建器必须：

* 返回一个 `FilterChain`，其 `filter_str` **不** 自行包裹在
  `[in_label]...[out_label]` — 管道会添加该包装（参见
  `CLAUDE.md` § 架构不变量）。
* 在给定相同的 `(params, in_label, rng)` 元组时应是确定性的。如果构建器使用随机性，请接受 `rng: random.Random | None = None` 并使用它，而不是自行构造 `Random(...)` ——否则恢复的运行将以非确定性方式分歧。
* 对每个新标签使用 `LabelAllocator`，永远不要硬编码 `v1`, `a3`，…

转换构建器绝对不能：

* 修改 `params` 或任何调用者提供的对象，
* 调用 `subprocess` 或读取文件系统（这是 `core/` 的问题），
* 在模块顶部导入可选依赖项——应推迟到第一次调用，这样缺失依赖会导致干净的错误，而不是导入时崩溃。

<a id="failure-modes-and-where-to-look"></a>

## 失败模式（以及查看位置）

|症状|可能原因|查看位置|
|---|---|---|
| `WARNING: third-party transform plugin '<name>' failed to load` |插件导入时引发错误|运行 `python -c "import <module>"` 并查看回溯|
|插件已安装但 `video-uniq probe --list-transforms` 未显示它|入口点名称拼写错误，或错误的组| `python -c "from importlib.metadata import entry_points as e; print(list(e(group='video_uniquifier.transforms')))"` |
|尽管已安装，`KeyError: 'video.pingpong'` 在 `video-uniq run` 上|配置文件在插件导入顺序之前加载 — 在干净的 venv 中卸载并重新安装|检查 `pip show <plugin>` 确认安装位置与 `python -c "import sys; print(sys.path)"` 匹配|
|在配置文件更改后恢复仍使用缓存状态|预期 — 计划哈希已更改，因此恢复缓存键不同。要么干净重启，要么恢复配置文件| `core/pipeline.py::compute_plan_hash` |

<a id="versioning"></a>

## 版本控制

`register` / `TransformSpec` / `FilterChain` / `LabelAllocator` 公共接口 **自 v0.8.0 起稳定**。破坏性更改只会在主版本升级时发生，并附带迁移指南的发行说明。
