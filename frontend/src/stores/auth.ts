import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

import { fetchMe } from '../services/api'
import api from '../services/api'

/** Формат ответа /users/me/ — телефон обязателен, остальное может быть не заполнено */
export interface UserProfile {
  id: string
  phone: string
  email?: string
  first_name?: string
  last_name?: string
  last_seen?: string | null
}

/** Обновляемые поля профиля (PATCH /users/me/) */
export type ProfileUpdatePayload = Partial<
  Pick<UserProfile, 'phone' | 'email' | 'first_name' | 'last_name'>
>

/** Декодируем JWT payload без запроса к API */
function getUserFromToken(): UserProfile | null {
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
  const user = ref<UserProfile | null>(getUserFromToken())
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

      // Загружаем полный профиль через /users/me/
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

      // Загружаем профиль через /users/me/ вместо использования data.user
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

  async function updateProfile(payload: ProfileUpdatePayload): Promise<boolean> {
    isLoading.value = true
    error.value = ''
    try {
      const { data } = await api.patch('/users/me/', payload)
      // Ответ — профиль целиком, в том же формате, что /users/me/
      user.value = data
      return true
    } catch (e: any) {
      const d = e.response?.data
      const fieldErrors: any[] = d && typeof d === 'object' ? Object.values(d) : []
      // DRF отвечает по полям ({phone: ['...']}); detail — у 429 и не-валидационных отказов
      error.value =
        (typeof d === 'string' ? d : d?.detail) ||
        fieldErrors.map((v) => (Array.isArray(v) ? v[0] : v)).filter(Boolean)[0] ||
        'Не удалось сохранить профиль'
      return false
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

  return {
    user,
    isLoading,
    error,
    isAuthenticated,
    login,
    register,
    updateProfile,
    logout,
    clearError,
  }
})
