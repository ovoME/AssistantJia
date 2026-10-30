import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it } from 'vitest'
import { routes } from './routes'

function createTestRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes,
  })
}

describe('application routes', () => {
  it('resolves the public and admin pages with their titles', () => {
    const router = createTestRouter()
    const expected = [
      ['/', 'reader', '小嘉 · 图书馆智能馆员'],
      ['/admin', 'admin', '管理端 · 数据看板'],
      ['/admin/data', 'admin-data', '管理端 · 数据管理'],
      ['/admin/settings', 'admin-settings', '管理端 · 系统设置'],
    ] as const

    for (const [path, name, title] of expected) {
      const resolved = router.resolve(path)
      expect(resolved.name).toBe(name)
      expect(resolved.meta.title).toBe(title)
    }
  })

  it('preserves repeated query parameters with the stable router API', () => {
    const router = createTestRouter()
    const resolved = router.resolve('/?q=popular&tag=history&tag=fiction')

    expect(resolved.name).toBe('reader')
    expect(resolved.fullPath).toBe('/?q=popular&tag=history&tag=fiction')
    expect(resolved.query).toEqual({
      q: 'popular',
      tag: ['history', 'fiction'],
    })
  })

  it('serializes named-route query values without changing the route path', () => {
    const router = createTestRouter()
    const resolved = router.resolve({
      name: 'admin-data',
      query: { tab: 'active', tag: ['history', 'fiction'] },
    })

    expect(resolved.path).toBe('/admin/data')
    expect(resolved.fullPath).toBe('/admin/data?tab=active&tag=history&tag=fiction')
  })
})
