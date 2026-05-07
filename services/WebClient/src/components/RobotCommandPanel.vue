<script setup lang="ts">
import { computed, ref, toRaw } from 'vue'
import type { RobotState, SocketStatus } from '../composables/useRobotSocket'
import KeyValueMap from './KeyValueMap.vue'

const props = defineProps<{
  status: SocketStatus
  messages: Record<string, unknown>[] | Readonly<Record<string, unknown>[]>,
  robotState: RobotState
}>()

const emit = defineEmits<{ send: [method: string], clear: [] }>()

const method = ref('')

function send() {
  if (!method.value.trim()) return
  emit('send', method.value.trim())
  method.value = ''
}


const reversed = computed(() => Array.from(props.messages).reverse())



</script>

<template>
  <section>
    <article>
      <KeyValueMap :map="robotState" />
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
