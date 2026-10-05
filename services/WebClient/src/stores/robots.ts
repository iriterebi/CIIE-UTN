import { defineStore } from "pinia";

import { ref, onMounted, readonly } from "vue";
import { useRouter } from "vue-router";
import { useApi } from "../composables/useApi";
import type { Robot } from "../types";
import { useAuthStore } from "./auth";

export const useRobotsStore = defineStore("robots", () => {
  const api = useApi();
  const router = useRouter();

  const robots = ref<Robot[]>([]);
  const loading = ref(true);
  const error = ref("");
  const auth = useAuthStore();

  async function loadRobots() {
    try {
      robots.value = await api.get<Robot[]>("/admin/robot/list");
    } catch (e) {
      error.value = (e as Error).message;
    } finally {
      loading.value = false;
    }
  }

  async function controlRobot(robot: Robot) {
    try {
      const tokenData = await auth.requestRobotUsagePermission(robot.id);
      router.push({
        path: `/robot/${robot.id}`,
        state: {
          robotAccessToken: tokenData.access_token,
          robotName: robot.name,
        },
      });
    } catch (e) {
      error.value = (e as Error).message;
    }
  }

  return ({
    robots,
    error,
    loading,
    controlRobot,
    loadRobots,
  });
});
