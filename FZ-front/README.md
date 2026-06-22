# FZ-front

高翠网移动端 H5 前端，基于 React + Vite 构建，覆盖游客找货、商家注册登录、商品发布、商品管理、账户权益和支付结果等页面。

## 技术栈

- React 19
- TypeScript
- Vite
- React Router
- ESLint

## 主要页面

- 首页 AI 匹配对话页
- 商品详情页
- 商家注册 / 登录页
- 商家工作台
- 发布商品 / 编辑商品页
- AI 发品结果页
- 商品管理页
- 商家客资页
- 账户信息 / VIP 权益页

## 本地配置

```bash
cp .env.example .env
```

前端环境文件中只保留本地开发所需的公开配置，例如 API Base URL。不要在前端仓库中写入任何私钥、服务端密码或支付密钥。

## 安装依赖

```bash
npm install
```

## 启动开发环境

```bash
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173
```

## 构建生产包

```bash
npm run build
```

构建产物输出到：

```text
FZ-front/dist
```

## 质量检查

```bash
npm run lint
npm run build
```

## 部署说明

前端适合部署为静态站点：

1. 执行 `npm run build`
2. 将 `dist` 目录发布到 Nginx 静态根目录
3. 对 SPA 路由启用 `try_files $uri $uri/ /index.html`
4. 将 `/api/` 反向代理到后端服务

## 说明

- 所有线上地址请通过环境变量注入，不要写死在文档或源码说明中。
- 详细业务背景和整体架构见仓库根目录 [README](../README.md)。
