<script setup lang="ts">
import { computed } from 'vue'
import type { RobotState, SocketStatus } from "../composables/useRobotSocket";
import KeyValueMap from './KeyValueMap.vue'

defineOptions({
  inheritAttrs: true
})


export interface RobotStatus {
    state: RobotState;
    status: SocketStatus;
}

const props = defineProps<RobotStatus>();

const  robotState = computed(() => {
  const { sensors, ...rest } = props.state
  return { sensors, rest }
})

</script>
<template>
    <div class="container">
        <article style="display: flex">
            <span style="margin-right: auto">Estado</span>
            <span :data-state="status" class="status">
              <kbd v-if="status === 'connected'">Conectado</kbd>
              <kbd v-else-if="status === 'connecting'" aria-busy="true">Conectando...</kbd>
              <kbd v-else-if="status === 'authenticating'" aria-busy="true">Autenticando...</kbd>
              <kbd v-else-if="status === 'reconnecting'" aria-busy="true">Reconectando...</kbd>
              <kbd v-else-if="status === 'error'">Error</kbd>
              <kbd v-else>Desconectado</kbd>
            </span>
        </article>
        <article>
            <KeyValueMap :map="robotState.rest" />
        </article>
        <article>
            <h4>Sensors</h4>
            <KeyValueMap id="sensors" :map="robotState.sensors" />
        </article>
    </div>
</template>

<style>
#sensors {
    font-family: monospace;
    background-color: #111827;
    padding: 0.5rem 1rem;
    border-radius: 0.5rem;

    .key {
        color:#4ADE80;
        font-weight: 400;
    }
}

.status {
    &[data-state=connected] {
        --pico-code-kbd-background-color: #DCFCE7;
        --pico-code-kbd-color: #1A7A3C
    }
}
</style>
