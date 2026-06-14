# 高翠网

移动端 H5 + FastAPI 后端骨架。当前阶段只完成前后端基础搭建，具体页面按 `doc/计划.md` 逐页开发。

## 目录

- `FZ-front`：React + Vite + TypeScript 移动端 H5
- `FZ-backend`：Python FastAPI + SQLAlchemy + Alembic
- `docker-compose.yml`：本地 PostgreSQL/pgvector、Redis、MinIO
- `doc/计划.md`：开发计划
- `doc/高翠网PRD.md`：产品 PRD
- `pic/`：页面原型图

## 本地依赖服务

```bash
docker compose up -d postgres redis minio
```

敏感配置不要写入代码。先按示例创建本地环境文件：

```bash
cp .env.example .env
cp FZ-backend/.env.example FZ-backend/.env
```

然后在 `.env` 填写 Docker 服务账号密码，在 `FZ-backend/.env.bak.codex` 填写后端数据库连接、
`SECRET_KEY`、MiMo API key 和 DashScope embedding 配置。后端实际读取 `FZ-backend/.env.bak.codex`。

MinIO 控制台：

```text
http://localhost:9001
```

## 启动后端

```bash
cd FZ-backend
cp .env.example .env.bak.codex
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://localhost:8000/api/health
```

后端验证：

```bash
cd FZ-backend
.venv/bin/ruff check .
.venv/bin/python -m pytest
```

## 启动前端

```bash
cd FZ-front
cp .env.example .env
npm run dev
```

默认地址：

```text
http://localhost:5173
```

前端验证：

```bash
cd FZ-front
npm run lint
npm run build
```
