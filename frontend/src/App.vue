<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from './stores/auth'
import { fetchMe } from './services/api'

const auth = useAuthStore()

onMounted(async () => {
  // При перезагрузке страницы загружаем полный профиль
  if (auth.isAuthenticated && (!auth.user?.first_name || !auth.user?.phone)) {
    try {
      const { data } = await fetchMe()
      auth.user = data
    } catch {
      // Токен невалиден — разлогиниваем
      auth.logout()
    }
  }
})
</script>

<template>
  <RouterView />
</template>
