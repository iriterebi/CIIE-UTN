<script setup lang="ts">
import { onUnmounted, ref, watch } from 'vue'
import { useVideoSocket } from '../composables/useVideoSocket'

const props = defineProps<{
  robotId: string
  robotAccessToken: string
  active: boolean
}>()

const canvasRef = ref<HTMLCanvasElement | null>(null)
const { status, error, connect, disconnect } = useVideoSocket()

watch(
  () => props.active,
  (active) => {
    if (active && canvasRef.value) {
      const ctx = canvasRef.value.getContext('2d')
      if (ctx) connect(props.robotId, props.robotAccessToken, ctx)
    } else {
      disconnect()
    }
  },
  { immediate: true }
)

onUnmounted(() => disconnect())
</script>

<template>
  <div>
    <canvas ref="canvasRef" style="max-width: 100%; background: #000;"></canvas>
    <p v-if="status !== 'connected'">
      <small v-if="status === 'error'">Video: {{ error }}</small>
      <small v-else>Video: {{ status }}...</small>
    </p>
  </div>
</template>
