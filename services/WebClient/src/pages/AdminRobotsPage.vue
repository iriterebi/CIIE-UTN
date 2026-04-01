<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useApi } from '../composables/useApi'
import type { Robot } from '../types'
import PendingRobotCard from '../components/PendingRobotCard.vue'
import RobotCard from '../components/RobotCard.vue'

const api = useApi()

const pending = ref<Robot[]>([])
const allRobots = ref<Robot[]>([])
const loading = ref(true)
const error = ref('')

async function loadData() {
  loading.value = true
  error.value = ''
  try {
    const [p, all] = await Promise.all([
      api.get<Robot[]>('/admin/robot/pending'),
      api.get<Robot[]>('/admin/robot/list'),
    ])
    pending.value = p
    allRobots.value = all
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}

async function approveRobot(robotId: string, approval: { name: string; description: string }) {
  try {
    await api.post(`/admin/robot/${robotId}/approve`, approval)
    await loadData()
  } catch (e) {
    error.value = (e as Error).message
  }
}

async function rejectRobot(robotId: string) {
  try {
    await api.post(`/admin/robot/${robotId}/reject`, {})
    await loadData()
  } catch (e) {
    error.value = (e as Error).message
  }
}

onMounted(loadData)
</script>

<template>
  <h2>Administración de Robots</h2>

  <p v-if="loading" aria-busy="true">Cargando...</p>
  <p v-if="error" role="alert">{{ error }}</p>

  <template v-if="!loading">
    <section v-if="pending.length > 0">
      <h3>Pendientes de aprobación</h3>
      <PendingRobotCard
        v-for="robot in pending"
        :key="robot.id"
        :robot="robot"
        @approve="approveRobot"
        @reject="rejectRobot"
      />
    </section>
    <p v-else><small>No hay robots pendientes.</small></p>

    <section>
      <h3>Todos los robots</h3>
      <RobotCard
        v-for="robot in allRobots"
        :key="robot.id"
        :robot="robot"
      />
    </section>
  </template>
</template>
