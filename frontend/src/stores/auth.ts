import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import { fetchMe } from '../services/api'
import api from '../services/api'

/** Декодируем JWT payload без запроса к API */
function getUserFromToken() {
  try {
    const token = localStorage.getItem('access_token')
    if (!token) return null
    const parts = token.split('.')
    if (parts.length !== 3) return null
    const payload = JSON.parse(atob(parts[1] as string))
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
      return null
    }
    // Возвращаем базовые данные из JWT, полный профиль загрузится в onMounted
    return {
      id: payload.user_id,
      phone: payload.phone || '',
      first_name: payload.first_name || '',
      last_name: payload.last_name || '',
    }
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

      // Загружаем полный профиль через /auth/me/
      try {
        const { data: profile } = await fetchMe()
        user.value = profile
      } catch {
        // Fallback если /me/ не сработал
        const parts = data.access.split('.')
        if (parts.length === 3) {
          const payload = JSON.parse(atob(parts[1] as string))
          user.value = {
            id: payload.user_id as string,
            phone,
            first_name: '',
            last_name: '',
          }
        }
      }
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

      // Загружаем профиль через /auth/me/ вместо использования data.user
      try {
        const { data: profile } = await fetchMe()
        user.value = profile
      } catch {
        user.value = data.user || null
      }
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
