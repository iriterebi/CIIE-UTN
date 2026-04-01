<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <nav class="container">
    <ul>
      <li><strong>Labs Remoto</strong></li>
    </ul>
    <ul>
      <template v-if="auth.isAuthenticated">
        <li><RouterLink to="/dashboard">Dashboard</RouterLink></li>
        <li v-if="auth.isAdmin"><RouterLink to="/admin/robots">Admin</RouterLink></li>
        <li><a href="#" @click.prevent="logout">Cerrar sesión</a></li>
      </template>
      <template v-else>
        <li><RouterLink to="/login">Iniciar sesión</RouterLink></li>
        <li><RouterLink to="/register">Registro</RouterLink></li>
      </template>
    </ul>
  </nav>
</template>
