<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import type { User } from '../stores/chat'

const props = defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()

const auth = useAuthStore()
const chatStore = useChatStore()

const query = ref('')
const users = ref<User[]>([])
const isSearching = ref(false)
const isBusy = ref(false)
const error = ref('')

const details = computed(() => chatStore.currentChatDetails)
const myIsAdmin = computed(() => !!details.value?.my_is_admin)
const memberIds = computed(() => new Set((details.value?.members ?? []).map((m) => m.id)))

const search = useDebounceFn(async (q: string) => {
  if (!q.trim()) { users.value = []; return }
  isSearching.value = true
  error.value = ''
  try {
    const { data } = await api.get('/users/search/', { params: { q: q.trim() } })
    const list: User[] = Array.isArray(data) ? data : data.results || []
    users.value = list.filter((u) => !memberIds.value.has(u.id))
  } catch { error.value = 'Ошибка поиска' }
  finally { isSearching.value = false }
}, 300)

watch(query, (val) => search(val))

watch(() => props.isOpen, (open) => {
  if (!open) { query.value = ''; users.value = []; error.value = '' }
})

async function addMember(userId: string) {
  if (!details.value || isBusy.value) return
  isBusy.value = true
  error.value = ''
  try {
    await api.post(`/chats/${details.value.id}/add-member/`, { user_id: userId })
    await chatStore.loadChatDetails(details.value.id)
    query.value = ''
    users.value = []
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Не удалось добавить участника'
  } finally {
    isBusy.value = false
  }
}

async function removeMember(userId: string) {
  if (!details.value || isBusy.value) return
  const isSelf = userId === auth.user?.id
  isBusy.value = true
  error.value = ''
  try {
    await api.post(`/chats/${details.value.id}/remove-member/`, { user_id: userId })
    if (isSelf) {
      // Сервер удаляет опустевший чат; в любом случае чат для нас закрыт
      chatStore.removeChat(details.value.id)
      emit('close')
    } else {
      await chatStore.loadChatDetails(details.value.id)
    }
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Не удалось удалить участника'
  } finally {
    isBusy.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="modal-overlay" @click.self="emit('close')">
      <div class="modal">
        <h3>Участники</h3>
        <div v-if="error" class="error-msg">{{ error }}</div>

        <div class="user-list">
          <div v-for="m in details?.members ?? []" :key="m.id" class="user-item member-item">
            <div class="member-info">
              <div class="user-item-name">
                {{ m.first_name || m.phone }}
                <span v-if="m.is_admin" class="member-badge admin">админ</span>
                <span v-if="m.id === auth.user?.id" class="member-badge">вы</span>
              </div>
              <div class="user-item-phone">{{ m.phone }}</div>
            </div>
            <button
              v-if="m.id === auth.user?.id || myIsAdmin"
              class="remove-member-btn"
              :disabled="isBusy"
              @click="removeMember(m.id)"
            >
              {{ m.id === auth.user?.id ? 'Выйти' : 'Удалить' }}
            </button>
          </div>
        </div>

        <template v-if="myIsAdmin">
          <input
            v-model="query"
            class="form-input"
            placeholder="Добавить участника: телефон или имя"
          />
          <div class="user-list add-list">
            <div v-if="isSearching" class="user-list-empty">Поиск...</div>
            <div v-else-if="users.length === 0 && query.trim()" class="user-list-empty">
              Не найдено
            </div>
            <div
              v-for="u in users"
              :key="u.id"
              class="user-item"
              @click="addMember(u.id)"
            >
              <div class="user-item-name">{{ u.first_name }} {{ u.last_name }}</div>
              <div class="user-item-phone">{{ u.phone }}</div>
            </div>
          </div>
        </template>

        <button class="btn-secondary" @click="emit('close')">Закрыть</button>
      </div>
    </div>
  </Teleport>
</template>
