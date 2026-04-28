# Web 服务

Web 服务将 QQMusicApi 暴露为 HTTP API。

## 1. 安装

```bash
git clone https://github.com/luren-dc/QQMusicApi
cd QQMusicApi
uv sync --group web
```

## 2. 启动服务

开发环境可使用 `uvicorn` 启动：

```bash
uv run uvicorn web.app:app
```

## 3. 查看 API 文档

打开 [http://localhost:8000/docs](http://localhost:8000/docs) 可以查看所有可用接口。
