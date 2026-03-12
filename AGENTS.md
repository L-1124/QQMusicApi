# AGENTS.md

## Dev environment

* Python：`>=3.10`
* 依赖管理：`uv`
* 构建后端：`hatchling`

### Setup commands

* 安装依赖：`uv sync`
* 运行 Python 测试：`uv run pytest`
* 运行 Ruff 检查：`uv run ruff check qqmusic_api tests`
* 运行 Pyrefly 检查：`uv run pyrefly check`
* 运行 Docs 构建：`uv run zensical build`
* 本地预提交检查：`uv run pre-commit run --all-files`

## Commit messages

* 使用 Conventional Commits：`<type>(<scope>): <subject>`。
* 提交信息使用中文。
* commit-msg 钩子会校验 Commitizen / Conventional Gitmoji 格式。

## Documentation rules

### Python

* Docstrings 使用 Google Style。
* public API、class、方法、函数必须有 docstring。
* 测试函数必须包含单行中文 docstring（英文标点）。
* `Args` / `Returns` / `Yields` / `Raises` 按需提供。
* 仅描述可观察行为，禁止描述实现细节。
* 类型检查以 `pyrefly` 为准，不使用 `basedpyright`。

### docs/

* 仅面向用户，描述 Usage 与 Behavior。
* 新增页面必须同步更新 `mkdocs.yml` 的 `nav`。
* 文档构建工具实际使用 `zensical`，站点配置文件是 `mkdocs.yml`。

## Tooling notes

* 运行时核心依赖包括：`anyio`、`httpx[http2]`、`orjson`、`pydantic v2`、`tarsio`、`httpx-ws`、`cryptography`。
* pre-commit 的本地 Python 钩子包括：`ruff --fix`、`ruff format`、`pyrefly check`。
* `docs build` 只在 `pre-push` 阶段运行；`ruff`、`ruff-format`、`pyrefly` 在 `pre-commit` 阶段运行。

## Agent behavior

* 每次回答都以 `皇上启奏:` 开头。
* **核心规约**：遵循 `docs/contributing.md` 中的详细规约。**在执行任务前，必须完整阅读该指南以确保合规。**
* 禁止在 Python 测试中模拟 Rust WireType，除非是明确的协议基线测试。
* 仅在明确要求时，才能 `git commit` 或 `git push`。
