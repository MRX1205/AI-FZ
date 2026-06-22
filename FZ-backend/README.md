# FZ-backend

高翠网后端服务，基于 FastAPI 构建，负责认证、聊天会话、AI 匹配、商家商品管理、客资和支付等业务能力。

## 技术栈

- FastAPI
- SQLAlchemy Async
- Alembic
- PostgreSQL
- pgvector
- httpx
- pytest

## 目录说明

```text
FZ-backend/
├── app/
│   ├── api/          # 路由层
│   ├── core/         # 配置和基础能力
│   ├── db/           # 数据库会话
│   ├── models/       # ORM 模型
│   ├── schemas/      # 请求/响应模型
│   └── services/     # AI、匹配、支付等服务编排
├── alembic/          # 数据库迁移
├── tests/            # 后端测试
└── README.md
```

## 本地配置

只根据示例创建环境文件，不要提交真实配置：

```bash
cp .env.example .env
```

需要自行填写的典型字段：

- 数据库连接
- `SECRET_KEY`
- `BACKEND_CORS_ORIGINS`
- MiMo / DashScope 配置
- 支付宝配置
- 公开访问域名

## 安装依赖

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

## 启动服务

```bash
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

## 核心模块

### 认证与商家会话

- 商家注册、登录、验证码发送
- 当前商家身份查询
- 商家资料维护

### AI 商品匹配

- 游客会话创建与消息记录
- 自由文本需求预处理
- 需求改写与结构化提取
- 向量召回与规则兜底
- 自然语言回复生成

### 商家 AI 发品

- 商品图片上传
- 多模态识别生成草稿
- 商品发布、编辑、删除
- embedding 刷新

### 支付

- 会员订单创建
- 支付结果回调
- 商家会员状态同步

## 质量检查

```bash
ruff check .
pytest
```

## 说明

- 上传资源目录需要具备读写权限。
- 生产环境请使用服务器侧私有环境变量，不要在仓库中保存任何线上密钥。
- 具体业务介绍请查看仓库根目录 [README](../README.md)。
