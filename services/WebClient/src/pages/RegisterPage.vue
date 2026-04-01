<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const form = ref({
  nombrecompleto: '',
  email: '',
  usr_name: '',
  usr_psw: '',
  statuss: 'alumno',
  usr_pronouns: '',
})
const confirmPassword = ref('')
const error = ref('')
const loading = ref(false)

async function submit() {
  if (form.value.usr_psw !== confirmPassword.value) {
    error.value = 'Las contraseñas no coinciden'
    return
  }
  error.value = ''
  loading.value = true
  try {
    await auth.signup(form.value)
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
      <h2>Registro</h2>
    </header>
    <form @submit.prevent="submit">
      <label>
        Nombre completo
        <input v-model="form.nombrecompleto" type="text" required />
      </label>
      <label>
        Email
        <input v-model="form.email" type="email" required />
      </label>
      <label>
        Usuario
        <input v-model="form.usr_name" type="text" required autocomplete="username" />
      </label>
      <label>
        Contraseña
        <input v-model="form.usr_psw" type="password" required autocomplete="new-password" />
      </label>
      <label>
        Confirmar contraseña
        <input v-model="confirmPassword" type="password" required autocomplete="new-password" />
      </label>
      <label>
        Pronombres
        <input v-model="form.usr_pronouns" type="text" placeholder="Opcional" />
      </label>
      <fieldset>
        <legend>Rol</legend>
        <label>
          <input type="radio" v-model="form.statuss" value="alumno" /> Alumno
        </label>
        <label>
          <input type="radio" v-model="form.statuss" value="profe" /> Profesor
        </label>
      </fieldset>
      <p v-if="error" role="alert"><small>{{ error }}</small></p>
      <button type="submit" :aria-busy="loading" :disabled="loading">Registrarse</button>
    </form>
    <footer>
      <small>¿Ya tenés cuenta? <RouterLink to="/login">Iniciá sesión</RouterLink></small>
    </footer>
  </article>
</template>
