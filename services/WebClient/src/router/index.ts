import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "../stores/auth";

import LoginPage from "../pages/LoginPage.vue";
import RegisterPage from "../pages/RegisterPage.vue";
import DashboardPage from "../pages/DashboardPage.vue";
import RobotControlPage from "../pages/RobotControlPage.vue";
import AdminRobotsPage from "../pages/AdminRobotsPage.vue";
import NotFoundPage from "../pages/NotFoundPage.vue";
import RobotAdminPage from "../pages/RobotAdminPage.vue";

declare module "vue-router" {
  interface RouteMeta {
    guest?: boolean;
    requiresAuth?: boolean;
    requiresAdmin?: boolean;
  }
}

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", component: LoginPage, meta: { guest: true } },
    { path: "/register", component: RegisterPage, meta: { guest: true } },

    {
      path: "/",
      meta: { requiresAuth: true },
      children: [
        { path: "dashboard", component: DashboardPage },
        { path: "robot/:id", component: RobotControlPage },
        {
          path: "admin",
          meta: { requiresAdmin: true },
          children: [
            { path: "robots", component: AdminRobotsPage },
            { path: "robots/:id", component: RobotAdminPage, name: "robot-admin" },
          ],
        },
      ],
    },
    { path: "/", redirect: "/dashboard" },
    { path: "/:pathMatch(.*)*", component: NotFoundPage },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();

  // Cargar usuario si hay token pero no se ha cargado
  if (auth.token && !auth.user) {
    await auth.fetchUser();
  }

  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return "/login";
  }

  if (to.meta.requiresAdmin && !auth.isAdmin) {
    return "/dashboard";
  }

  if (to.meta.guest && auth.isAuthenticated) {
    return "/dashboard";
  }
});

export default router;
