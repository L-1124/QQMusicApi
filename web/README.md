# Web Port 使用说明

## 1. 安装与运行

### 克隆仓库

```bash
git clone https://github.com/luren-dc/QQMusicApi
```

### 依赖安装

```bash
uv sync --group web
```

### 启动服务

```bash
uv run uvicorn web.app:app --host 0.0.0.0 --port 8000 --reload
```

## 2. API 文档

访问 [http://localhost:8000/docs](http://localhost:8000/docs) 查看自动生成的 API 文档，了解可用的接口和参数。
