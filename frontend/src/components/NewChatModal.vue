<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import api from '../services/api'
import { useChatStore } from '../stores/chat'
import type { User } from '../stores/chat'

const props = defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()

const query = ref('')
const users = ref<User[]>([])
const isLoading = ref(false)
const error = ref('')

const chatStore = useChatStore()

// Debounced поиск через VueUse
const search = useDebounceFn(async (q: string) => {
  if (!q.trim()) { users.value = []; return }
  isLoading.value = true
  error.value = ''
  try {
    const { data } = await api.get('/users/search/', { params: { q: q.trim() } })
    users.value = Array.isArray(data) ? data : data.results || []
  } catch { error.value = 'Ошибка поиска' }
  finally { isLoading.value = false }
}, 300)

watch(query, (val) => search(val))

// Очистка при закрытии
watch(() => props.isOpen, (open) => {
  if (!open) { query.value = ''; users.value = []; error.value = '' }
})

async function createChat(userId: string) {
  error.value = ''
  try {
    await api.post('/chats/private/', { interlocutor_id: userId })
    await chatStore.loadChats()
    emit('close')
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Ошибка создания чата'
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="modal-overlay" @click.self="emit('close')">
      <div class="modal">
        <h3>Новый чат</h3>
        <div v-if="error" class="error-msg">{{ error }}</div>
        <input v-model="query" class="form-input" placeholder="Телефон или имя" autofocus />
        <div class="user-list">
          <div v-if="isLoading" class="user-list-empty">Поиск...</div>
          <div v-else-if="users.length === 0 && query.trim()" class="user-list-empty">Не найдено</div>
          <div v-for="u in users" :key="u.id" class="user-item" @click="createChat(u.id)">
            <div class="user-item-name">{{ u.first_name }} {{ u.last_name }}</div>
            <div class="user-item-phone">{{ u.phone }}</div>
          </div>
        </div>
        <button class="btn-secondary" @click="emit('close')">Отмена</button>
      </div>
    </div>
  </Teleport>
</template>
