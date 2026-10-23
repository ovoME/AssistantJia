import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'reader',
      component: () => import('@/views/reader/ChatView.vue'),
      meta: { title: '小嘉 · 图书馆智能馆员' },
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('@/views/admin/DashboardView.vue'),
      meta: { title: '管理端 · 数据看板' },
    },
  ],
})

router.afterEach((to) => {
  document.title = (to.meta.title as string) || '小嘉'
})

export default router
