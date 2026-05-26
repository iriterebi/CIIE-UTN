<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    router.push('/dashboard')
  } catch (e) {
    error.value = (e as Error).message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <article>
    <header>
      <h2>Iniciar sesión</h2>
    </header>
    <form @submit.prevent="submit">
      <label>
        Usuario
        <input v-model="username" type="text" required autocomplete="username" />
      </label>
      <label>
        Contraseña
        <input v-model="password" type="password" required autocomplete="current-password" />
      </label>
      <p v-if="error" role="alert"><small>{{ error }}</small></p>
      <button type="submit" :aria-busy="loading" :disabled="loading">Entrar</button>
    </form>
    <footer>
      <small>¿No tenés cuenta? <RouterLink to="/register">Registrate</RouterLink></small>
    </footer>
  </article>
</template>
