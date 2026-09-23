<script setup lang="ts">
import { ref, watch } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import api from '../services/api'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import type { User } from '../stores/chat'

const props = defineProps<{ isOpen: boolean }>()
const emit = defineEmits<{ close: [] }>()

const chatStore = useChatStore()
const auth = useAuthStore()

const mode = ref<'private' | 'group'>('private')
const groupName = ref('')
const query = ref('')
const users = ref<User[]>([])
const selectedUsers = ref<User[]>([])
const isLoading = ref(false)
const isCreating = ref(false)
const error = ref('')

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

function reset() {
  mode.value = 'private'
  groupName.value = ''
  query.value = ''
  users.value = []
  selectedUsers.value = []
  error.value = ''
}

// Очистка при закрытии
watch(() => props.isOpen, (open) => {
  if (!open) reset()
})

watch(mode, () => {
  query.value = ''
  users.value = []
  error.value = ''
})

function isSelected(u: User): boolean {
  return selectedUsers.value.some((s) => s.id === u.id)
}

function toggleSelect(u: User) {
  if (u.id === auth.user?.id) return
  const idx = selectedUsers.value.findIndex((s) => s.id === u.id)
  if (idx >= 0) selectedUsers.value.splice(idx, 1)
  else selectedUsers.value.push(u)
}

function removeSelected(u: User) {
  selectedUsers.value = selectedUsers.value.filter((s) => s.id !== u.id)
}

async function createPrivate(userId: string) {
  if (isCreating.value) return
  error.value = ''
  isCreating.value = true
  try {
    const { data } = await api.post('/chats/private/', { interlocutor_id: userId })
    await chatStore.loadChats()
    emit('close')
    chatStore.selectChat(data.id)
  } catch (e: any) {
    error.value = e.response?.data?.detail || 'Ошибка создания чата'
  } finally {
    isCreating.value = false
  }
}

async function createGroup() {
  if (isCreating.value) return
  if (!groupName.value.trim()) {
    error.value = 'Введите название группы'
    return
  }
  error.value = ''
  isCreating.value = true
  try {
    const { data } = await api.post('/chats/', {
      type: 'GROUP',
      name: groupName.value.trim(),
      member_ids: selectedUsers.value.map((u) => u.id),
    })
    await chatStore.loadChats()
    emit('close')
    chatStore.selectChat(data.id)
  } catch (e: any) {
    const d = e.response?.data
    error.value =
      (typeof d === 'string' ? d : d?.name?.[0] || d?.member_ids?.[0] || d?.detail) ||
      'Ошибка создания чата'
  } finally {
    isCreating.value = false
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="isOpen" class="modal-overlay" @click.self="emit('close')">
      <div class="modal">
        <h3>Новый чат</h3>
        <div v-if="error" class="error-msg">{{ error }}</div>

        <div class="mode-tabs">
          <button
            class="mode-tab"
            :class="{ active: mode === 'private' }"
            @click="mode = 'private'"
          >
            Личный чат
          </button>
          <button
            class="mode-tab"
            :class="{ active: mode === 'group' }"
            @click="mode = 'group'"
          >
            Групповой чат
          </button>
        </div>

        <template v-if="mode === 'group'">
          <input
            v-model="groupName"
            class="form-input"
            placeholder="Название группы"
          />
          <div v-if="selectedUsers.length" class="chip-list">
            <span v-for="u in selectedUsers" :key="u.id" class="chip">
              {{ u.first_name || u.phone }}
              <button class="chip-remove" @click="removeSelected(u)">×</button>
            </span>
          </div>
        </template>

        <input v-model="query" class="form-input" placeholder="Телефон или имя" autofocus />
        <div class="user-list">
          <div v-if="isLoading" class="user-list-empty">Поиск...</div>
          <div v-else-if="users.length === 0 && query.trim()" class="user-list-empty">Не найдено</div>
          <div
            v-for="u in users"
            :key="u.id"
            class="user-item"
            :class="{ selected: mode === 'group' && isSelected(u), disabled: mode === 'group' && u.id === auth.user?.id }"
            @click="mode === 'group' ? toggleSelect(u) : createPrivate(u.id)"
          >
            <div class="user-item-name">
              {{ u.first_name }} {{ u.last_name }}
              <span v-if="mode === 'group' && isSelected(u)" class="member-badge">✓</span>
            </div>
            <div class="user-item-phone">{{ u.phone }}</div>
          </div>
        </div>

        <template v-if="mode === 'group'">
          <button
            class="btn-primary"
            :disabled="isCreating || !groupName.trim()"
            @click="createGroup"
          >
            {{ isCreating ? '...' : `Создать группу${selectedUsers.length ? ` (${selectedUsers.length + 1})` : ''}` }}
          </button>
        </template>
        <button class="btn-secondary" @click="emit('close')">Отмена</button>
      </div>
    </div>
  </Teleport>
</template>
