# 高翠网 AI 翡翠商品匹配系统

高翠网是一个面向翡翠交易场景的 AI 供需撮合项目，包含游客智能找货、商家 AI 发品、商家后台管理和 VIP 权益支付等核心流程。项目采用前后端分离架构，前端是移动端 H5，后端提供商品、会话、支付和 AI 能力编排接口。

本仓库聚焦真实业务链路，不内置任何生产密钥、数据库密码或第三方平台证书。请始终通过 `.env.example` 衍生本地环境文件，并在部署时使用服务器侧私有配置。

## 核心能力

- AI 商品匹配：将游客自由文本需求解析为预算、品类、颜色、种水、用途等结构化信息，再结合向量召回和规则重排输出商品卡片。
- AI 发品文案生成：商家上传商品图片后，自动生成标题、简介、详情、标签、价格参考和匹配参数，先形成草稿再由商家确认发布。
- 语义检索体系：商品侧统一生成 `search_text`，并使用 pgvector 存储 embedding，用于语义召回和后续推荐扩展。
- 商家后台：提供注册登录、商品发布、商品编辑、客资查看、账号信息和 VIP 权益页面。
- 支付链路：支持商家购买 VIP 套餐，并预留支付宝回调和订单同步能力。

## 技术栈

### 前端

- React 19
- TypeScript
- Vite
- React Router

### 后端

- Python 3.12
- FastAPI
- SQLAlchemy Async
- Alembic
- PostgreSQL
- pgvector
- httpx

### AI 与外部能力

- MiMo：文本对话、多模态图片识别、需求改写、自然语言回复
- DashScope Embedding：商品和需求向量生成
- 支付宝：VIP 支付

## 主要业务流程

### 1. 游客 AI 找货

1. 用户进入首页创建或恢复聊天会话。
2. 输入自由文本需求，例如“10 万预算 帝王绿手镯”。
3. 后端先判断是否是直接翡翠需求，必要时进行需求改写。
4. 系统提取预算、品类、颜色、种水、用途等结构化字段。
5. 优先走向量检索召回候选商品，失败时再走规则兜底。
6. 结合预算接近度、参数命中、VIP 权重和商品更新时间重排结果。
7. 返回自然语言回复和商品卡片，前端以聊天流式体验展示。

### 2. 商家 AI 发品

1. 商家登录后进入发布页。
2. 上传最多 6 张商品图片。
3. 后端保存图片并调用 AI 识别商品内容。
4. 生成标题、简介、详情、标签、价格参考和匹配参数。
5. 系统写入商品草稿，商家可继续修改。
6. 商家确认发布后，后端校验完整性并刷新商品 embedding。

### 3. 商家 VIP 支付

1. 商家在账户页选择 VIP 套餐。
2. 后端创建订单并返回支付链接。
3. 支付平台回调后端通知接口。
4. 系统更新订单状态和商家会员状态。
5. 前端刷新结果页和账号权益展示。

## 仓库结构

```text
AI-FZ/
├── FZ-front/              # React + Vite 移动端 H5
├── FZ-backend/            # FastAPI + SQLAlchemy + Alembic
├── deploy/                # 部署相关目录
├── doc/                   # 产品、分析和过程文档
├── pic/                   # 原型和截图资源
├── docker-compose.yml     # 本地 PostgreSQL / Redis / MinIO
└── README.md
```

## 本地开发

### 1. 准备环境变量

不要直接复制任何线上环境文件到仓库。仅根据示例创建本地配置：

```bash
cp .env.example .env
cp FZ-backend/.env.example FZ-backend/.env
cp FZ-front/.env.example FZ-front/.env
```

需要自行填写的内容通常包括：

- 数据库连接
- `SECRET_KEY`
- MiMo / DashScope API Key
- 支付回调域名
- 前后端公开访问地址

请确保真实密钥仅保存在本地机器、CI 密钥库或服务器环境中，不要写入 Git。

### 2. 启动依赖服务

```bash
docker compose up -d postgres redis minio
```

如果只做前后端联调，也可以改用你自己的 PostgreSQL / Redis 环境。

### 3. 启动后端

```bash
cd FZ-backend
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
alembic upgrade head
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

默认后端地址：

```text
http://127.0.0.1:8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

### 4. 启动前端

```bash
cd FZ-front
npm install
npm run dev
```

默认前端地址：

```text
http://127.0.0.1:5173
```

## 质量检查

### 前端

```bash
cd FZ-front
npm run lint
npm run build
```

### 后端

```bash
cd FZ-backend
ruff check .
pytest
```

## API 模块概览

后端统一由 `/api` 前缀暴露接口，主要模块如下：

- `/api/auth`：商家注册、登录、验证码、当前用户信息
- `/api/chat`：游客聊天会话、消息记录、商品匹配
- `/api/merchant`：商品草稿、AI 生成、商品管理、客资、商家资料
- `/api/products`：公开商品详情、联系卖家
- `/api/payments`：VIP 订单、支付回调和支付结果
- `/api/health`：健康检查

## AI 实现说明

### AI 匹配

- 输入：游客自由文本需求
- 中间处理：需求改写、结构化提取、统一 `search_text`
- 检索：embedding + pgvector 余弦相似度召回
- 兜底：关键词规则匹配
- 输出：自然语言回复 + 商品卡片

### AI 发品

- 输入：商家上传的商品图片
- 中间处理：图片保存、转 data URL、多模态识别
- 生成字段：标题、简介、详情、标签、价格、匹配参数
- 输出：商品草稿，商家确认后发布

## 部署说明

项目支持普通 Linux 服务器部署，不依赖 Docker 才能运行应用本身。常见部署方式：

1. 前端执行 `npm run build`，将 `FZ-front/dist` 发布到 Nginx 静态目录。
2. 后端使用虚拟环境安装依赖，通过 `uvicorn` 或 `gunicorn + uvicorn worker` 运行。
3. 使用 Nginx 反向代理 `/api/` 到后端端口，并为前端提供 SPA 路由回退。
4. 数据库、Redis、支付证书和 API Key 均保留在服务器环境中配置。

部署时请重点检查：

- CORS 白名单
- 前后端公开域名
- 数据库连接串
- 支付回调地址
- 上传目录读写权限

## 安全说明

- 仓库中不应提交任何 `.env`、真实证书、私钥、支付密钥或云服务账号。
- 所有第三方密钥均应通过环境变量或服务器私有文件注入。
- 对外分享仓库前，请再次检查提交历史中是否包含敏感信息。

## 相关文档

- [后端说明](./FZ-backend/README.md)
- [前端说明](./FZ-front/README.md)
- `doc/`：产品、分析和项目文档
