# AGENTS.md

## Dev environment

* 依赖管理：`uv`

### Setup commands

* 安装依赖：`uv sync`
* 运行 Python 测试：`uv run pytest`

## Commit messages

* 使用 Conventional Commits：`<type>(<scope>): <subject>`。
* 提交信息使用中文。

## Documentation rules

### Python

* Docstrings 使用 Google Style。
* public API/class/方法/函数必须有 docstring。
* 测试函数必须包含单行中文 docstring（英文标点）。
* `Args` / `Returns` / `Yields` / `Raises` 按需提供。
* 仅描述可观察行为，禁止描述实现细节。

### docs/

* 仅面向用户，描述 Usage 与 Behavior。
* 新增页面必须同步更新 `mkdocs.yml` 的 `nav`。

## Agent behavior

* 每次回答都以 `皇上启奏:` 开头。
* **核心规约**：遵循 `CONTRIBUTING.md` 中的详细规约。**在执行任务前，必须完整阅读该指南以确保合规。**
* 禁止在 Python 测试中模拟 Rust WireType，除非是明确的协议基线测试。
* 仅在明确要求时，才能 `git commit` 或 `git push`。
