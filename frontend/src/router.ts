// designed by mew
import { createRouter, createWebHistory } from 'vue-router';
import HomeView from './views/HomeView.vue';

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', component: HomeView },
    { path: '/index.html', redirect: '/' },
    { path: '/admin/:pathMatch(.*)*', component: () => import('./management/AdminView.vue') },
    { path: '/research/', component: () => import('./views/ResearchView.vue') },
    { path: '/publications/', component: () => import('./views/PublicationsView.vue') },
    { path: '/publications/:id/', component: () => import('./views/PublicationView.vue') },
    { path: '/people/', component: () => import('./views/PeopleView.vue') },
    { path: '/projects/', component: () => import('./views/ProjectsView.vue') },
    { path: '/projects/:slug/', component: () => import('./views/ProjectView.vue') },
    { path: '/news/', component: () => import('./views/NewsView.vue') },
    { path: '/join/', component: () => import('./views/JoinView.vue') },
    { path: '/:slug/', component: () => import('./views/CustomPageView.vue') },
    { path: '/:pathMatch(.*)*', component: () => import('./views/NotFoundView.vue') },
  ],
  async scrollBehavior(to, _from, savedPosition) {
    // Wait for the route's leave animation before measuring anchors in its successor.
    await new Promise((resolve) => setTimeout(resolve, 210));
    if (savedPosition) return savedPosition;
    if (to.hash) return { el: to.hash, top: 32, behavior: 'smooth' };
    return { top: 0 };
  },
});
