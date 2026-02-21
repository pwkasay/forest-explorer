import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/DashboardView.vue'),
  },
  {
    path: '/map',
    name: 'map',
    component: () => import('@/views/MapView.vue'),
  },
  {
    path: '/qa',
    name: 'qa',
    component: () => import('@/views/QAView.vue'),
  },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
