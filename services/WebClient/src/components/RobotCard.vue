<script setup lang="ts">
import type { Robot } from '../types'

defineProps<{ robot: Robot }>()
defineEmits<{ control: [robot: Robot] }>()
</script>

<template>
  <article>
    <header>
      <strong>{{ robot.name || robot.external_identifier }}</strong>
      <small> — {{ robot.status }}</small>
    </header>
    <p v-if="robot.description">{{ robot.description }}</p>
    <footer v-if="robot.status === 'approved'">
      <button @click="$emit('control', robot)">Controlar</button>
    </footer>
  </article>
</template>
