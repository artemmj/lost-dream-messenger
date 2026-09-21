import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../services/api'

/** Декодируем JWT payload без запроса к API */
function getUserFromToken() {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return null  // 👈 null уже обрабатывается выше

    const parts = token.split('.')
    if (parts.length < 3) return null  // 👈 Защита от malformed JWT

    const payload = JSON.parse(atob(parts[1]))  // ✅ parts[1] гарантированно string

    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return null
    }

    return { id: payload.user_id, phone: payload.phone || '' }
  } catch {
    return null
  }
}

export const useAuthStore = defineStore('auth', () => {
  // State — восстанавливаем из токена при перезагрузке
  const user = ref(getUserFromToken())
  const isLoading = ref(false)
  const error = ref('')

  const isAuthenticated = computed(() => !!user.value)

  async function login(phone: string, password: string) {
    isLoading.value = true
    error.value = ''
    try {
      const { data } = await api.post('/auth/login/', { phone, password })
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)

      // ✅ Безопасный decode
      const parts = data.access.split('.')
      const payload = parts.length === 3 ? JSON.parse(atob(parts[1])) : {}
      user.value = { id: payload.user_id, phone }
    } catch (e: any) {
      error.value = e.response?.data?.detail || 'Ошибка входа'
    } finally {
      isLoading.value = false
    }
  }

  async function register(form: Record<string, string>) {
    isLoading.value = true
    error.value = ''
    try {
      const { data } = await api.post('/auth/register/', form)
      localStorage.setItem('access_token', data.access)
      localStorage.setItem('refresh_token', data.refresh)
      user.value = data.user
    } catch (e: any) {
      const d = e.response?.data
      error.value = typeof d === 'string' ? d : d?.detail || JSON.stringify(d) || 'Ошибка'
    } finally {
      isLoading.value = false
    }
  }

  function logout() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    user.value = null
  }

  function clearError() { error.value = '' }

  return { user, isLoading, error, isAuthenticated, login, register, logout, clearError }
})
