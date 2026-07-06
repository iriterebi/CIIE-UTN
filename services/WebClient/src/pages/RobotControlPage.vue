<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useRobotSocket } from '../composables/useRobotSocket'
import RobotCommandPanel from '../components/RobotCommandPanel.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const { status, robotStatus, messages, error, connect, sendCommand, disconnect, clearMessagesHistory, robotState } = useRobotSocket()

const robotId = route.params.id as string
const robotAccessToken = history.state.robotAccessToken as string | undefined
const robotName = history.state.robotName as string | undefined

onMounted(() => {
  if (!robotAccessToken || !auth.token) {
    router.push('/dashboard')
    return
  }
  connect(robotId, robotAccessToken)
})

onUnmounted(() => {
  disconnect()
})
</script>

<template>
  <hgroup>
    <h2>{{ robotName || robotId }}</h2>
    <p>
      Estado:
      <span v-if="status === 'connected'">Conectado</span>
      <span v-else-if="status === 'connecting'" aria-busy="true">Conectando...</span>
      <span v-else-if="status === 'authenticating'" aria-busy="true">Autenticando...</span>
      <span v-else-if="status === 'reconnecting'" aria-busy="true">Reconectando...</span>
      <span v-else-if="status === 'error'">Error: {{ error }}</span>
      <span v-else>Desconectado</span>
    </p>
    <p v-if="status === 'connected' && robotStatus !== 'robot_disponible'">
      <span v-if="robotStatus === 'robot_desconectado_reconectando'" aria-busy="true">
        El robot se desconectó, reconectando...
      </span>
      <span v-else-if="robotStatus === 'robot_no_disponible'">
        El robot no está disponible.
      </span>
    </p>
  </hgroup>

  <RobotCommandPanel
    :status="status"
    :messages="messages"
    :robotState="robotState"
    @send="sendCommand"
    @clear="clearMessagesHistory"
  />
</template>
