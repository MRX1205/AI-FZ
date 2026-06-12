import { Bot, ChevronRight, Gem } from 'lucide-react'
import { Link } from 'react-router-dom'
import { routeGroups, type AppRoute } from '../routes'

type PlaceholderPageProps = {
  route: AppRoute
  groupTitle: string
}

export function PlaceholderPage({ route, groupTitle }: PlaceholderPageProps) {
  return (
    <article className="page">
      <header className="page-header">
        <div className="brand-mark">
          <span className="brand-logo" aria-hidden="true">
            <Gem size={21} />
          </span>
          高翠网
        </div>
        <span className="status-pill">
          <Bot size={15} />
          骨架已就绪
        </span>
      </header>

      <section className="hero-panel">
        <p className="eyebrow">{groupTitle}</p>
        <h1 className="page-title">{route.title}</h1>
        <p className="page-copy">
          当前页面为开发骨架占位。后续会按照 PRD 与对应原型图逐页复刻视觉、
          交互、跳转和接口联调。
        </p>
      </section>

      {route.path === '/' ? (
        <nav className="route-section" aria-label="开发页面入口">
          {routeGroups.map((group) => (
            <section className="route-section" key={group.title}>
              <h2 className="section-title">{group.title}</h2>
              <ul className="route-list">
                {group.routes.map((item) => (
                  <li key={item.path}>
                    <Link className="route-item" to={item.examplePath ?? item.path}>
                      <span className="route-meta">
                        <span className="route-name">{item.title}</span>
                        <span className="route-path">{item.path}</span>
                      </span>
                      <ChevronRight className="route-state" size={18} />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </nav>
      ) : (
        <section className="route-section">
          <h2 className="section-title">计划状态</h2>
          <p className="page-copy">
            该路由已纳入开发计划。页面开发时会保留此路径，并替换为真实 H5 页面。
          </p>
        </section>
      )}
    </article>
  )
}
