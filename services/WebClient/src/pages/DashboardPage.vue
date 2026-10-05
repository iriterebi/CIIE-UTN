<script setup lang="ts">
import { onMounted } from "vue";
import RobotCard from "../components/RobotCard.vue";
import { useAuthStore } from "../stores/auth";
import { useRobotsStore } from "../stores/robots";

const auth = useAuthStore();
const robots = useRobotsStore();

onMounted(robots.loadRobots)
</script>

<template>
    <h2>Hola, {{ auth.user?.nombrecompleto || auth.user?.usr_name }}</h2>

    <p v-if="robots.loading" aria-busy="true">Cargando robots...</p>
    <p v-else-if="robots.error" role="alert">{{ robots.error }}</p>
    <p v-else-if="robots.robots.length === 0">No hay robots registrados.</p>

    <div v-else>
        <RobotCard
            v-for="robot in robots.robots"
            :key="robot.id"
            :robot="robot"
            @control="robots.controlRobot"
        />
    </div>
</template>
