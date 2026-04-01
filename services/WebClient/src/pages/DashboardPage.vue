<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useApi } from '../composables/useApi'
import { useAuthStore } from '../stores/auth'
import type { Robot } from '../types'
import RobotCard from '../components/RobotCard.vue'

const api = useApi()
const auth = useAuthStore()
const router = useRouter()

const robots = ref<Robot[]>([])
const loading = ref(true)
const error = ref('')

onMounted(async () => {
  try {
    robots.value = await api.get<Robot[]>('/admin/robot/list')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
})

async function controlRobot(robot: Robot) {
  try {
    const tokenData = await api.post<{ access_token: string }>('/auth/request_robot_access', {
      robot_id: String(robot.id),
    })
    router.push({
      path: `/robot/${robot.id}`,
      state: { robotAccessToken: tokenData.access_token, robotName: robot.name },
    })
  } catch (e) {
    error.value = (e as Error).message
  }
}
</script>

<template>
  <h2>Hola, {{ auth.user?.nombrecompleto || auth.user?.usr_name }}</h2>

  <p v-if="loading" aria-busy="true">Cargando robots...</p>
  <p v-else-if="error" role="alert">{{ error }}</p>
  <p v-else-if="robots.length === 0">No hay robots registrados.</p>

  <div v-else>
    <RobotCard
      v-for="robot in robots"
      :key="robot.id"
      :robot="robot"
      @control="controlRobot"
    />
  </div>
</template>
