<script setup lang="ts">
import { ref } from 'vue'
import type { Robot } from '../types'

defineProps<{ robot: Robot }>()

const emit = defineEmits<{
  approve: [robotId: string, approval: { name: string; description: string }]
  reject: [robotId: string]
}>()

const name = ref('')
const description = ref('')

function approve(robot: Robot) {
  if (!name.value.trim()) return
  emit('approve', robot.id, { name: name.value.trim(), description: description.value.trim() })
}
</script>

<template>
  <article>
    <header>
      <strong>{{ robot.external_identifier }}</strong>
      <small> — pendiente de aprobación</small>
    </header>
    <form @submit.prevent="approve(robot)">
      <label>
        Nombre
        <input v-model="name" placeholder="Nombre del robot" required />
      </label>
      <label>
        Descripción
        <input v-model="description" placeholder="Descripción (opcional)" />
      </label>
      <div role="group">
        <button type="submit">Aprobar</button>
        <button type="button" class="secondary" @click="$emit('reject', robot.id)">Rechazar</button>
      </div>
    </form>
  </article>
</template>
