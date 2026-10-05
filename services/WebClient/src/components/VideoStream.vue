<script setup lang="ts">
import { onUnmounted, ref, watch } from "vue";
import { useVideoSocket } from "../composables/useVideoSocket";

defineOptions({
  inheritAttrs: true
})

const props = defineProps<{
    robotId: string;
    robotAccessToken: string;
    active: boolean;
}>();

const canvasRef = ref<HTMLCanvasElement | null>(null);
const { status, error, connect, disconnect } = useVideoSocket();

watch(
    () => props.active,
    (active) => {
        if (active && canvasRef.value) {
            const ctx = canvasRef.value.getContext("2d");
            if (ctx) connect(props.robotId, props.robotAccessToken, ctx);
        } else {
            disconnect();
        }
    },
    { immediate: true },
);

onUnmounted(() => disconnect());
</script>

<template>
    <article>
        <canvas
            ref="canvasRef"
            style="max-width: 100%; background: #000"
        ></canvas>
        <p v-if="status !== 'connected'" class="info">
            <kbd>
                <small v-if="status === 'error'">{{ error }}</small>
                <small v-else>{{ status }}...</small>
            </kbd>
        </p>
    </article>
</template>
<style scoped>
article {
    display: flor-root;
    padding-inline: 0;
    padding-top: 0;
    contain: content;
}

canvas {
    width: 100%;
}

.info {
    margin-bottom: 0;
    padding-inline: 1rem;
    padding-top: 1rem;
}
</style>
