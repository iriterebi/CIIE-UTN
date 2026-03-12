<script setup lang="ts">
import { ref } from 'vue'
import type { SocketStatus } from '../composables/useRobotSocket'

defineProps<{
  status: SocketStatus
  messages: Record<string, unknown>[]
}>()

const emit = defineEmits<{ send: [method: string] }>()

const method = ref('')

function send() {
  if (!method.value.trim()) return
  emit('send', method.value.trim())
  method.value = ''
}
</script>

<template>
  <section>
    <form @submit.prevent="send">
      <fieldset role="group">
        <input
          v-model="method"
          placeholder="Comando (ej: move_arm)"
          :disabled="status !== 'connected'"
        />
        <button type="submit" :disabled="status !== 'connected'">Enviar</button>
      </fieldset>
    </form>

    <h4>Respuestas</h4>
    <div v-if="messages.length === 0">
      <p><small>Sin respuestas aún.</small></p>
    </div>
    <pre v-for="(msg, i) in messages" :key="i"><code>{{ JSON.stringify(msg, null, 2) }}</code></pre>
  </section>
</template>
