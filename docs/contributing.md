# 贡献指南

感谢您对本项目的兴趣！为了确保项目的高质量和一致性，请遵循以下指南进行贡献。

## 先决条件

* **Python 3.10+**
* **git**
* [**uv**](https://docs.astral.sh/uv/)
* [**pre-commit**](https://pre-commit.com/)

## 开发流程

### 配置开发环境

```bash
# 安装 uv
# https://docs.astral.sh/uv/

# 在 GitHub 上分叉存储库并在本地克隆您的分叉。
git clone git@github.com:<your username>/QQMusicApi.git
cd QQMusicApi

# 安装开发依赖
uv sync

# 安装 Git hooks
uv run pre-commit install
uv run pre-commit install --hook-type commit-msg
```

### API 编写

查看[**编写指南**](coding.md)

### 本地检查

在提交前，请至少运行以下检查:

```bash
# 运行测试
uv run pytest

# 运行 Ruff 与类型检查
uv run ruff check qqmusic_api tests
uv run pyrefly check

# 按当前 pre-commit 配置执行全部检查
uv run pre-commit run --all-files
```

### 构建文档

如果您对文档进行了任何更改（包括对将出现在 API 文档中的函数签名、类定义或文档字符串的更改），请确保其构建成功。

```bash
# 构建文档
uv run zensical build
```

### 在线文档

```bash
uv run mkdocs serve
```

### 创建 Pull Request

> [!NOTE]
> 请向 `main` 分支发起 [Pull Request](https://github.com/l-1124/QQMusicApi/pulls)

提交更改，将分支推送到 GitHub，然后创建拉取请求。

请遵循拉取请求模板并填写尽可能多的信息。链接到任何相关问题，并说明行为变化、兼容性影响和验证结果。

## 代码规范

* 代码风格遵循 [Google Python Style](https://google.github.io/styleguide/pyguide.html)
* 代码格式遵循 [PEP8](https://www.python.org/dev/peps/pep-0008/)
* Lint 使用 [Ruff](https://docs.astral.sh/ruff/)
* 类型检查使用 `pyrefly`

## 代码注释

* 注释内容包括：模块注释、类注释、函数注释、参数类型注释、返回值注释
* 注释风格遵循 [Google-style docstrings](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
* 测试函数应包含单行中文 docstring（英文标点）

## 文档规范

* 文档构建工具使用 [zensical](https://github.com/zensical/zensical)
* 文档使用 [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) 构建
* API 文档使用 [mkdocstrings](https://mkdocstrings.github.io/) 构建

### Markdown 拓展语法

* [PyMdown Extensions](https://facelessuser.github.io/pymdown-extensions/extensions)
  ([Material for MkDocs](https://squidfunk.github.io/mkdocs-material/reference/))

## 提交规范

本项目采用 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/v1.0.0/)
规范。
