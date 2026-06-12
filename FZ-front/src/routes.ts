export type AppRoute = {
  path: string
  title: string
  examplePath?: string
}

export type RouteGroup = {
  title: string
  routes: AppRoute[]
}

export const routeGroups: RouteGroup[] = [
  {
    title: '买家端',
    routes: [
      { path: '/', title: 'AI聊天找货首页' },
      { path: '/product/:id', title: '商品详情页', examplePath: '/product/demo-product' },
    ],
  },
  {
    title: '商家端',
    routes: [
      { path: '/merchant/auth', title: '商家登录/注册' },
      { path: '/merchant/dashboard', title: '商家后台' },
      { path: '/merchant/publish', title: '发布商品-上传图片' },
      { path: '/merchant/publish/result', title: '发布商品-AI生成结果' },
      { path: '/merchant/publish/edit', title: '发布商品-确认编辑' },
      { path: '/merchant/products', title: '商品管理' },
      {
        path: '/merchant/products/:id/edit',
        title: '商品编辑',
        examplePath: '/merchant/products/demo-product/edit',
      },
      { path: '/merchant/leads', title: '客资列表' },
      { path: '/merchant/leads/:id', title: '客资详情', examplePath: '/merchant/leads/demo-lead' },
      { path: '/merchant/account', title: '账户权限' },
      { path: '/merchant/profile', title: '个人中心' },
      { path: '/merchant/notifications', title: '系统通知' },
    ],
  },
]
