# 高翠网项目分析报告（供新 AI 快速接手）

版本基线：基于当前仓库代码与 `doc` 目录文档整理  
整理时间：2026-06-13  
适用对象：新接手本项目的 AI / 工程协作代理

---

## 1. 项目一句话说明

高翠网是一个 **翡翠找货平台**，当前形态是 **移动端 H5 前端 + FastAPI 后端**。  
面向两类用户：

1. **买家端**：通过 AI 聊天描述翡翠需求，浏览商品详情，并表达购买意向。
2. **商家端**：通过邮箱验证码登录，管理商品、发布商品、查看客资、查看通知、管理账户与会员权限。

当前仓库不是纯原型，也不是完整商用成品，而是：

- 已有一批 **真实可运行页面与接口**；
- 部分页面仍为 **占位页**；
- 后端内置了 **大量 seed/mock 数据逻辑**，用于前后端联调与演示；
- AI 能力已接入接口层，但整体仍处于 **首版闭环实现阶段**。

---

## 2. 仓库结构

```text
AI-FZ/
├─ README.md                 项目总说明
├─ doc/
│  ├─ 计划.md               开发计划
│  ├─ 高翠网PRD.md          产品需求文档
│  └─ 项目分析报告-AI交接.md  本文档
├─ FZ-front/                前端：React + Vite + TypeScript H5
├─ FZ-backend/              后端：FastAPI + SQLAlchemy + Alembic
├─ pic/                     原型图
└─ uploads/                 运行期上传目录
```

补充：

- `FZ-front/dist` 已存在，说明前端曾构建过。
- `FZ-front/node_modules` 已存在，说明前端依赖已安装。
- `FZ-backend/.venv` 已存在，说明后端虚拟环境已准备过。

---

## 3. 当前技术栈

### 3.1 前端

- React
- Vite
- TypeScript
- React Router
- lucide-react 图标库
- 原生 fetch 封装的 API Client
- 单份全局 CSS（非组件库方案）

特征：

- 明确按 **移动端 H5** 设计；
- 外层有手机壳式容器，宽度限制在 430px 内；
- 未引入复杂状态管理库，状态主要放在页面组件和 localStorage。

### 3.2 后端

- Python 3.12+
- FastAPI
- SQLAlchemy 2.x
- Alembic
- Pydantic / pydantic-settings
- httpx（调用外部 AI）

### 3.3 数据与基础设施

- PostgreSQL
- Redis（配置中声明，但当前代码使用痕迹不重）
- MinIO / 本地 uploads 静态文件目录
- `pgvector` 只在规划文档中提及，当前代码中未见实际接入

---

## 4. 项目目标与业务定位

根据 `README.md`、`doc/计划.md`、`doc/高翠网PRD.md`，项目核心目标是：

1. 用 AI 帮买家更快表达并澄清翡翠需求；
2. 将买家需求引导到商品与商家；
3. 为商家提供轻量后台，完成商品发布、客资承接、账号管理；
4. 用免费/VIP 分层做商家能力区分；
5. 为后续更强的 AI 能力（识图、商品文案生成、匹配推荐）预留接口。

可以把当前产品理解为：

- 前台：**AI 导购 + 商品承接**
- 后台：**商家商品管理 + 客资管理 + 会员分层**

---

## 5. 已实现功能总览

这里区分“代码已实现”和“文档规划但未完全实现”。

### 5.1 买家端已实现

1. **AI 聊天首页**
   - 支持游客进入；
   - 自动生成 `visitorId`；
   - 支持创建聊天会话；
   - 支持发送消息；
   - 支持刷新后从 localStorage 恢复聊天记录；
   - 支持重新从后端同步当前会话消息。

2. **聊天后端会话机制**
   - 创建聊天 session；
   - 拉取 session 消息；
   - 发送消息并返回一组“用户消息 + AI 回复”。

3. **AI 回复能力**
   - 已接 MiMo 模型接口；
   - 当前以文本回复为主；
   - 系统提示词已围绕“翡翠找货助手”设定。

### 5.2 商家端已实现

1. **邮箱验证码登录/注册**
   - 发送验证码；
   - 验证码登录；
   - 首次登录自动创建商家；
   - 登录后生成 session token；
   - 支持登出；
   - 支持 `/api/auth/me` 获取当前登录态。

2. **商家后台首页**
   - 显示商家等级；
   - 显示上架商品数 / 上限；
   - 显示今日客资、累计客资；
   - 显示最近客资列表；
   - 提供商品、客资、账户等入口。

3. **个人中心**
   - 获取商家资料；
   - 展示会员信息；
   - 发送修改邮箱验证码；
   - 修改邮箱；
   - 更新通知设置；
   - 退出登录。

4. **账户权限页**
   - 前端已实现展示页；
   - 用于展示免费/VIP 差异。

5. **商品管理**
   - 商品列表；
   - 按状态筛选：`all/listed/draft/unlisted`；
   - 查看单个商品；
   - 编辑商品；
   - 上架/下架；
   - 删除商品。

6. **发布商品流程**
   - 获取当前发布草稿；
   - 上传商品图片；
   - 删除草稿图片；
   - 调用 AI 生成商品文案草稿；
   - 发布商品。

7. **商品图片管理**
   - 单独替换商品图片；
   - 支持排序索引替换；
   - 上传图片会落到本地 `uploads`。

8. **客资管理**
   - 获取客资列表；
   - 获取客资详情；
   - VIP 可更新客资状态；
   - 免费商家会被遮罩买家邮箱。

9. **通知中心**
   - 获取通知列表；
   - 根据会员等级过滤通知类型。

### 5.3 已有但不完整 / 占位实现

1. **商品详情页**：路由已规划，但当前未接入真实页面实现。  
2. **发布商品 AI 结果独立页**：路由存在于规划中，但当前前端主实现更偏向在发布页内完成。  
3. **部分免费版/VIP版差异页面**：有些只体现在数据/展示差异，不是完整双页面。  
4. **系统帮助、关于我们**：文档提到跳转诉求，但当前未形成完整页面。  
5. **部分路由仍由 `PlaceholderPage` 占位**。

---

## 6. 前端分析

## 6.1 前端整体结构

前端核心入口：

- `FZ-front/src/main.tsx`
- `FZ-front/src/App.tsx`
- `FZ-front/src/routes.ts`

设计特点：

- `AppShell` 提供统一移动端容器；
- `App.tsx` 直接声明所有路由；
- `routes.ts` 既是路由说明表，也是占位页的数据来源；
- 未实现的路由自动映射为 `PlaceholderPage`。

这意味着：

- 当前前端是 **单体页面式结构**；
- 以页面为中心，而不是复杂组件体系；
- 适合快速推进原型到功能闭环；
- 后续如果页面持续增多，组件与样式拆分压力会变大。

## 6.2 前端路由状态

### 已实现页面

- `/` 买家 AI 聊天首页
- `/merchant/auth` 商家登录/注册
- `/merchant/dashboard` 商家后台
- `/merchant/leads` 客资列表
- `/merchant/leads/:id` 客资详情
- `/merchant/notifications` 系统通知
- `/merchant/products` 商品管理
- `/merchant/products/:id/edit` 商品编辑
- `/merchant/account` 账户权限
- `/merchant/profile` 个人中心
- `/merchant/publish` 发布商品
- `/merchant/publish/edit/:id` 发布商品编辑页

### 文档中规划但当前未真实实现或未接入

- `/product/:id`
- `/merchant/publish/result`
- `/merchant/publish/edit`（规划路径与真实实现路径已有差异，真实代码是 `/merchant/publish/edit/:id`）

这是一个很重要的信息：

> **文档规划和实际代码路由，已经出现了少量偏移。**

新 AI 接手时，不应只信 PRD，必须以 `App.tsx` 和 `routes.ts` 为准校对当前真实状态。

## 6.3 前端页面职责

### 1）HomePage

职责：

- 买家聊天主入口；
- 管理 visitorId、sessionId、messages 本地缓存；
- 调用聊天接口；
- 展示 AI 回复；
- 为后续商品卡片承接预留 UI 结构。

特点：

- 有明确版本号 `CURRENT_STORAGE_VERSION`，用于失效旧缓存；
- 对“会话不存在”做了重建逻辑；
- 是当前买家端最核心页面。

### 2）MerchantAuthPage

职责：

- 发送验证码；
- 进行验证码登录；
- 登录后写入 localStorage；
- 跳转商家后台。

特点：

- 当前验证码是开发态固定码；
- 前端已按真实登录流程接 API，不只是纯静态页。

### 3）MerchantDashboardPage

职责：

- 拉取后台统计信息；
- 渲染商家等级、商品数、客资数；
- 展示最近客资；
- 提供后台导航入口。

### 4）MerchantProfilePage

职责：

- 展示账号资料；
- 修改邮箱；
- 切换通知设置；
- 登出。

### 5）MerchantAccountPage

职责：

- 展示会员权益页；
- 根据是否 VIP 渲染不同内容。

### 6）MerchantProductsPage

职责：

- 商品列表；
- 商品状态筛选；
- 删除商品；
- 进入编辑页。

### 7）MerchantProductEditPage

职责：

- 编辑已有商品；
- 上/下架；
- 删除；
- 上传或替换图片。

### 8）MerchantPublishPage

职责：

- 取当前草稿；
- 上传图片；
- 调 AI 生成文案；
- 直接发布。

特点：

- 当前发布流程已不是纯“多步空壳”，而是具备实用后端闭环；
- 商品配额逻辑已接入。

### 9）MerchantPublishEditPage

职责：

- 对某个商品做发布前/发布中的编辑。

### 10）MerchantLeadsPage / MerchantLeadDetailPage

职责：

- 客资列表与详情；
- VIP 支持状态变更；
- 免费商家在数据层面受到权限限制。

### 11）MerchantNotificationsPage

职责：

- 展示通知消息流。

### 12）PlaceholderPage

职责：

- 用于未完成功能的占位；
- 明确告诉协作者该页面未开发完成。

这对新 AI 很重要：

> 项目并非“所有路由都要立即补完”，现有策略是允许未完成页面保留骨架占位。

## 6.4 前端状态管理方式

当前前端没有引入 Redux / Zustand / MobX / Pinia 这类库，而是：

- 页面局部 `useState`
- `useEffect` 拉取接口
- `localStorage` 持久化关键状态

主要持久化数据：

- 买家聊天 sessionId
- 买家聊天消息
- visitorId
- 商家登录 session

优点：

- 简单；
- 改动成本低；
- 适合当前阶段。

缺点：

- 页面间共享逻辑较分散；
- 登录态、缓存一致性、数据失效策略容易散落在多个页面。

## 6.5 前端 API 调用层

`src/api/client.ts` 提供：

- `apiGet`
- `apiPost`
- `apiPatch`
- `apiDelete`
- `apiUpload`
- `apiAssetUrl`
- `ApiError`

特点：

- 非 axios，而是基于原生 `fetch` 封装；
- 统一抛 `ApiError`；
- 统一从后端 `detail` 提取报错；
- `/uploads/` 资源会自动拼接 API host。

这是一个相对清晰、轻量的 API 层，足以支撑当前规模。

---

## 7. 后端分析

## 7.1 后端整体结构

后端主入口：

- `FZ-backend/app/main.py`

主要模块：

- `app/api/`：路由层
- `app/models/`：数据库模型
- `app/schemas/`：请求/响应模型
- `app/services/`：服务层，目前最核心是 `jade_agent.py`
- `app/core/`：配置
- `app/db/`：数据库 base 与 session

结构上是标准 FastAPI 分层，虽然服务层还不厚，但骨架清楚。

## 7.2 后端路由模块

### health

- `GET /api/health`

用途：

- 健康检查。

### auth

- `POST /api/auth/send-code`
- `POST /api/auth/login`
- `GET /api/auth/me`
- `POST /api/auth/logout`

用途：

- 商家验证码登录体系。

### chat

- `POST /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}/messages`
- `POST /api/chat/sessions/{session_id}/messages`

用途：

- 买家聊天会话与消息交互。

### merchant

包含以下能力：

1. **dashboard**
   - `GET /api/merchant/dashboard`

2. **profile**
   - `GET /api/merchant/profile`
   - `POST /api/merchant/profile/email-code`
   - `PATCH /api/merchant/profile/email`
   - `PATCH /api/merchant/profile/notifications`

3. **products**
   - `GET /api/merchant/products`
   - `GET /api/merchant/products/current-draft`
   - `POST /api/merchant/products/drafts/images`
   - `POST /api/merchant/products/drafts/generate`
   - `GET /api/merchant/products/{product_id}`
   - `PATCH /api/merchant/products/{product_id}`
   - `PATCH /api/merchant/products/{product_id}/publish`
   - `PATCH /api/merchant/products/{product_id}/status`
   - `DELETE /api/merchant/products/{product_id}`
   - `DELETE /api/merchant/products/{product_id}/images/{image_index}`
   - `POST /api/merchant/products/{product_id}/images/replace`

4. **leads**
   - `GET /api/merchant/leads`
   - `GET /api/merchant/leads/{lead_id}`
   - `PATCH /api/merchant/leads/{lead_id}/status`

5. **notifications**
   - `GET /api/merchant/notifications`

可以看出：

> 当前最重的业务逻辑都集中在 `merchant.py`，它是本项目后端的核心文件。

## 7.3 数据模型

### Merchant

字段表达了商家账号与会员能力：

- `email`
- `tier`：`free` / `vip`
- `vip_started_at`
- `vip_expires_at`
- `web_notification_enabled`
- `email_notification_enabled`

说明：

- 当前没有用户名、密码体系；
- 账号唯一标识主要是邮箱；
- 会员系统已经有起止时间字段，但更像首版实现。

### AuthCode

用途：

- 存验证码；
- 控制失效时间；
- 支持标记已使用。

### MerchantSession

用途：

- 保存登录 token；
- 保存 session 过期时间。

说明：

- 当前不是 JWT，而是数据库 session token。

### MerchantProduct

字段：

- 标题、摘要、详情
- 标签
- 价格（分）
- 状态
- 图片 URL 列表
- 发布时间

状态：

- `draft`
- `listed`
- `unlisted`

### MerchantProductImage

用途：

- 独立管理商品图片实体；
- 带 `sort_order`；
- 与 `MerchantProduct.image_urls` 形成“双轨”存储。

这是当前数据设计里一个值得注意的点：

> 商品图片既有结构化表，也有产品表上的 `image_urls` JSON 字段，存在一定冗余。

### MerchantLead

用途：

- 存买家意向线索；
- 包括邮箱、留言、商品标题、价格、图片、状态。

### MerchantNotification

用途：

- 存通知消息流；
- 当前类型至少包括 `new_lead`、`vip_expiring`。

### ChatSession / ChatMessage

用途：

- 支撑买家 AI 聊天；
- 消息可附带 `matched_products`。

说明：

- 当前商品卡片匹配能力的数据结构已预留；
- 但系统提示词明确说当前阶段不要承诺已找到具体商品，也不要输出商品卡片；
- 即：**结构预留了，产品逻辑还没真正放开。**

---

## 8. AI 能力分析

核心文件：`FZ-backend/app/services/jade_agent.py`

## 8.1 已实现的 AI 能力

### 1）买家聊天助手

通过 `JadeAgent.reply()` / `reply_text()` 调用外部 MiMo 模型。

系统提示词目标明确：

- 你是高翠 AI；
- 专注翡翠找货；
- 引导用户补充预算、品类、尺寸、品相、用途；
- 遇到无关问题要礼貌收束；
- 当前阶段不要声称已经找到具体商品。

这说明当前 AI 的定位不是“万能聊天”，而是 **垂直导购助手**。

### 2）商品文案生成

通过 `generate_product_copy_from_images()`：

- 输入图片 URL 列表；
- 请求 MiMo 多模态能力；
- 返回结构化 JSON；
- 生成 `title/summary/detail/tags/priceCents`。

这已经是一个非常关键的业务能力：

> 商家上传翡翠图片后，AI 帮他生成商品发布初稿。

## 8.2 AI 相关现状

1. 已接外部模型，但供应商是 `MiMo`，不是 OpenAI。  
2. 配置项中使用：
   - `mimo_api_key`
   - `mimo_base_url`
   - `mimo_model`
3. 若未配置 key，会直接返回提示。  
4. 若 AI 调用失败，会返回统一错误信息。  
5. 商品文案生成要求 AI 严格输出 JSON。  
6. 代码里存在 `_fallback_product_copy()`，但主流程是否启用 fallback 需要进一步关注具体调用链。

## 8.3 AI 能力边界

当前 AI **没有真正做成** 的能力：

- 向量检索商品匹配
- 基于库存的真实推荐
- 买家意图结构化抽取入库
- 自动生成客资
- 自动推送商家
- 识别翡翠真假/品质评级

也就是说，AI 目前偏向：

- 文案理解与追问
- 图片转商品草稿

还不是完整“智能撮合引擎”。

---

## 9. 权限与会员分层

本项目的商业化主线之一是免费/VIP 区分。

## 9.1 免费商家限制

根据当前代码，可确认的限制包括：

1. **商品上架数量限制**：免费商家上限 2 个；VIP 100 个。  
2. **客资隐私受限**：免费商家只能看到脱敏后的买家邮箱。  
3. **客资状态操作受限**：更新客资状态需要 VIP。  
4. **通知类型受限**：免费商家通知类型较少。

## 9.2 VIP 商家能力

1. 更高商品配额；  
2. 查看完整买家邮箱；  
3. 可操作客资状态；  
4. 可看到更多通知类型；  
5. 页面展示上带有 VIP 身份信息。

这部分在产品上很清晰，且代码里已有明确体现，不只是 PRD 文字。

---

## 10. 当前数据策略：大量 seed / mock 驱动

后端 `merchant.py` 中存在多组自动种子逻辑：

- `_seed_products_if_empty`
- `_seed_leads_if_empty`
- `_seed_notifications_if_empty`

含义：

- 新商家登录后，如果没有商品/客资/通知，系统会自动补一批演示数据；
- VIP 商家会补更多商品；
- 这让前端页面可以在无真实运营数据时跑通。

这说明当前阶段非常明确：

> 项目处于“功能闭环优先、真实运营其次”的开发期。

新 AI 接手时要注意两点：

1. 不要把这些 seed 数据误判成真实业务规则；  
2. 后续如果进入生产化阶段，这些逻辑大概率要收敛或移出主接口流程。

---

## 11. 测试覆盖情况

后端已有测试文件：

- `test_auth.py`
- `test_chat.py`
- `test_health.py`
- `test_merchant_dashboard.py`
- `test_merchant_leads.py`
- `test_merchant_products.py`
- `test_merchant_profile.py`

这说明：

- 后端核心接口已有一定回归保障；
- 登录、聊天、后台、客资、商品、个人中心都被覆盖到了；
- 项目不是“纯手工点点看”的状态。

前端方面：

- 当前未见对应测试体系；
- 更偏向人工联调 + 构建验证。

---

## 12. 文档与代码的一致性分析

这是给新 AI 最重要的一节。

## 12.1 一致的地方

1. 整体产品方向一致：买家 AI 找货 + 商家后台。  
2. 前后端技术栈与总 README 基本一致。  
3. 商家核心模块与计划文档一致：商品、客资、账户、通知。  
4. AI 文案生成能力与计划中的“AI 接入预留”一致。

## 12.2 不一致或已偏移的地方

1. **README 说前端是 React**，而 `doc/计划.md` 里的“前端技术栈”仍写成偏规划描述，需以当前代码为准。  
2. **部分 PRD 页面说明非常细，但代码并未全部逐页实现。**  
3. **规划路由与真实路由有差异**：
   - 文档里有 `/merchant/publish/edit`
   - 实际代码是 `/merchant/publish/edit/:id`
4. **商品详情页在 PRD 中重要，但当前代码未成为真实页面主实现。**  
5. **通知、帮助中心、关于我们等文档诉求未完全落地。**

结论：

> 当前项目应被理解为“按 PRD 推进中的可运行版本”，而不是“PRD 已完整落地”。

---

## 13. 当前项目最核心的真实闭环

如果只抓最重要的可运行链路，当前闭环是：

### 闭环 A：买家 AI 咨询

1. 买家进入首页  
2. 创建聊天 session  
3. 输入翡翠需求  
4. 后端调用 AI 返回导购式回复  
5. 聊天记录可恢复

### 闭环 B：商家登录与后台管理

1. 商家验证码登录  
2. 进入后台  
3. 查看商品、客资、通知、个人中心  
4. 使用会员分层能力

### 闭环 C：商家发布商品

1. 商家进入发布页  
2. 上传翡翠图片  
3. AI 生成商品文案  
4. 商家确认/编辑  
5. 商品发布到管理列表

这是目前最接近“产品骨架已经成型”的部分。

---

## 14. 当前项目的薄弱点 / 风险点

以下不是批评，而是帮助新 AI 快速避坑。

## 14.1 文档与实现存在偏差

PRD 很完整，但当前代码并未 1:1 覆盖所有页面与交互。新 AI 不能按 PRD 直接假设“都做完了”。

## 14.2 merchant.py 过重

`FZ-backend/app/api/routes/merchant.py` 承载了大量：

- 权限校验
- seed 逻辑
- 商品管理
- 发布流程
- 客资逻辑
- 通知逻辑
- 图片存储逻辑

这会导致：

- 修改风险较集中；
- 业务边界不够清楚；
- 后续继续扩展时容易变成“超级路由文件”。

## 14.3 商品图片数据有双轨冗余

- `merchant_products.image_urls`
- `merchant_product_images`

二者同时存在，后续要特别注意一致性。

## 14.4 当前更像演示版而非生产版

体现在：

- 登录验证码固定为 `123456`；
- 自动 seed 演示数据；
- 部分页面仍是占位；
- 真实支付、真实通知、真实客资流转均未形成完整闭环。

## 14.5 AI 接入已用，但业务约束较强

AI 当前被限制成“导购追问 + 文案生成”，不是商品搜索引擎。若新 AI 误以为项目已有“智能匹配库存”，会做出错误判断。

---

## 15. 给新 AI 的工作原则建议

如果新的 AI 要继续接手这个项目，建议遵循下面的理解顺序：

1. **先看真实代码，再看 PRD。**  
2. **路由以前端 `App.tsx` 为准。**  
3. **接口以 FastAPI 路由文件为准。**  
4. **会员能力以 `merchant.py` 当前逻辑为准。**  
5. **不要把 seed/mock 逻辑当成最终业务真相。**  
6. **涉及商品发布流程时，同时核对前端页面和后端 products 接口。**  
7. **涉及 AI 能力时，先看 `jade_agent.py`，不要凭空扩展产品能力。**

---

## 16. 新 AI 接手时建议优先阅读的文件

### 产品与项目层

- `README.md`
- `doc/计划.md`
- `doc/高翠网PRD.md`

### 前端层

- `FZ-front/src/App.tsx`
- `FZ-front/src/routes.ts`
- `FZ-front/src/api/client.ts`
- `FZ-front/src/types/domain.ts`
- `FZ-front/src/pages/HomePage.tsx`
- `FZ-front/src/pages/MerchantDashboardPage.tsx`
- `FZ-front/src/pages/MerchantPublishPage.tsx`
- `FZ-front/src/pages/MerchantProductEditPage.tsx`
- `FZ-front/src/pages/MerchantProfilePage.tsx`
- `FZ-front/src/pages/MerchantLeadsPage.tsx`

### 后端层

- `FZ-backend/app/main.py`
- `FZ-backend/app/core/config.py`
- `FZ-backend/app/api/router.py`
- `FZ-backend/app/api/routes/auth.py`
- `FZ-backend/app/api/routes/chat.py`
- `FZ-backend/app/api/routes/merchant.py`
- `FZ-backend/app/services/jade_agent.py`
- `FZ-backend/app/models/*.py`
- `FZ-backend/tests/*.py`

---

## 17. 当前项目状态总结

一句话总结：

> 这是一个已经跑通“买家 AI 对话 + 商家登录后台 + 商品发布管理 + 客资管理”主闭环的翡翠 H5 项目，但仍保留明显的开发期特征，包括占位页、seed 数据、固定验证码和部分 PRD 未完全落地。

再具体一点：

- **它不是空壳**：很多页面和接口是真的；
- **它也不是成品**：仍有明显未完成部分；
- **它最成熟的模块**：商家侧后台与商品发布链路；
- **它最关键的智能能力**：AI 聊天追问 + 图片生成商品文案；
- **它最需要谨慎理解的地方**：PRD、当前代码、seed 数据之间的边界。

---

## 18. 适合给新 AI 的简版认知卡片

你可以把下面这段直接给新的 AI：

```text
这是一个叫“高翠网”的翡翠找货项目，技术上是 React + Vite 的移动端 H5 前端，FastAPI + SQLAlchemy 的后端。产品分买家端和商家端：买家端通过 AI 聊天描述翡翠需求；商家端通过邮箱验证码登录后管理商品、客资、通知和个人中心。当前已经实现了商家登录、商家后台、商品列表/编辑/发布、客资列表/详情、通知列表、个人中心，以及买家 AI 聊天主页面。后端有大量 seed/mock 数据逻辑，方便空库演示，不要把这些种子数据当成最终业务规则。AI 目前主要做两件事：买家聊天追问，以及商家上传商品图片后生成商品文案草稿；还没有真正做成商品语义检索或完整智能匹配。项目文档较完整，但 PRD 与当前代码存在少量偏差，接手时应优先以前端 App.tsx 路由和后端 FastAPI 路由文件为准。```

---

## 19. 最终结论

如果新 AI 的目标是“快速理解这个项目并继续协作”，那么它应该先建立以下判断：

1. 这是 **H5 电商/撮合型项目**，垂直领域是翡翠；  
2. 当前阶段重点不是“商城交易”，而是 **找货、发布、承接客资**；  
3. 代码里已经有真实业务闭环，不应把它当纯 Demo；  
4. 同时它也保留开发期特征，不应把现状当最终生产架构；  
5. 若后续要继续开发，最值得关注的是：
   - 商家商品发布链路
   - 客资与会员分层
   - AI 能力如何从“生成/追问”升级到“真实匹配”

