import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useApi } from '../composables/useApi'

export interface User {
  id: number
  nombrecompleto: string
  email: string
  usr_name: string
  statuss: 'profe' | 'alumno'
  usr_pronouns: string | null
}

interface LoginResponse {
  access_token: string
  token_type: string
}

interface SignupResponse {
  user: User
  token: LoginResponse
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user = ref<User | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.statuss === 'profe')

  async function login(username: string, password: string) {
    const api = useApi()
    const data = await api.postForm<LoginResponse>('/auth/login', { username, password })
    token.value = data.access_token
    localStorage.setItem('token', data.access_token)
    await fetchUser()
  }

  async function signup(userData: Record<string, string>) {
    const api = useApi()
    const data = await api.post<SignupResponse>('/auth/signup', userData)
    token.value = data.token.access_token
    localStorage.setItem('token', data.token.access_token)
    user.value = data.user
  }

  async function fetchUser() {
    const api = useApi()
    try {
      user.value = await api.get<User>('/auth/me')
    } catch {
      logout()
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, isAuthenticated, isAdmin, login, signup, fetchUser, logout }
})
