<script setup lang="ts">
import { computed, defineEmits, defineProps, ref } from 'vue';
import type { SocketStatus } from '../composables/useRobotSocket';

const props = defineProps<{
  status: SocketStatus
  messages: Record<string, unknown>[] | Readonly<Record<string, unknown>[]>,
}>()

const emit = defineEmits<{ send: [method: string], clear: [] }>()

const method = ref('')

function send() {
  if (!method.value.trim()) return
  emit('send', method.value.trim())
  method.value = ''
}

function sendCommand(command: string) {
  emit('send', command)
}

const reversed = computed(() => Array.from(props.messages).reverse().slice(0, 5))



</script>

<template>
  <section>
      <article>
          <button @click="sendCommand('start')">Iniciar</button>
          <button @click="sendCommand('stop')">Parar</button>
          <button @click="sendCommand('restart')">Reiniciar</button>
      </article>

    <form @submit.prevent="send">
      <fieldset role="group">
        <input v-model="method" placeholder="Comando (ej: move_arm)" :disabled="status !== 'connected'" />
        <button type="submit" :disabled="status !== 'connected'">Enviar</button>
      </fieldset>
    </form>

    <div>
      <h4>Respuestas</h4>
      <button type="button" @click="emit('clear')">Limpiar</button>
    </div>
    <div v-if="messages.length === 0">
      <p><small>Sin respuestas aún.</small></p>
    </div>
    <pre v-for="(msg, i) in reversed" :key="i"><code>{{ JSON.stringify(msg, null, 2) }}</code></pre>
  </section>
</template>
