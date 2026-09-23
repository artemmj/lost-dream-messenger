<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import NewChatModal from './NewChatModal.vue'

const auth = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()
const showModal = ref(false)

/**
 * Отображаемое имя пользователя.
 * Приоритет: first_name → phone → "Пользователь"
 */
const displayName = computed(() => {
  const u = auth.user
  if (!u) return ''
  // Проверяем что значение существует И не пустая строка
  if (u.first_name && u.first_name.trim()) return u.first_name
  if (u.phone && u.phone.trim()) return u.phone
  return 'Пользователь'
})

const wsStatusColor = computed(() => ({
  connected: '#4caf50', connecting: '#ff9800', disconnected: '#e74c3c', error: '#e74c3c',
}[chatStore.wsStatus]))

const wsStatusLabel = computed(() => ({
  connected: 'на связи', connecting: 'подключение...', disconnected: 'нет соединения', error: 'нет соединения',
}[chatStore.wsStatus]))

function handleLogout() {
  chatStore.closeChat()
  auth.logout()
  router.push('/login')
}

function getChatName(chat: any): string {
  if (chat.name) return chat.name
  if (chat.interlocutor) return chat.interlocutor.first_name || chat.interlocutor.phone
  return chat.type === 'GROUP' ? 'Групповой чат' : 'Личный чат'
}

const formatUnread = (n: number) => (n > 99 ? '99+' : String(n))
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-user">
        <span class="sidebar-user-name">Привет, {{ displayName }}</span>
        <span
          v-if="chatStore.selectedChatId"
          class="ws-indicator"
          title="Статус WebSocket-соединения"
        >
          <span class="ws-dot" :style="{ background: wsStatusColor }" />
          {{ wsStatusLabel }}
        </span>
      </div>
      <button class="logout-btn" @click="handleLogout">Выйти</button>
    </div>
    <div class="chat-list">
      <div
        v-for="chat in chatStore.chats"
        :key="chat.id"
        class="chat-item"
        :class="{ active: chatStore.selectedChatId === chat.id, unread: chat.unread_count > 0 }"
        @click="chatStore.selectChat(chat.id)"
      >
        <div class="chat-item-name">{{ getChatName(chat) }}</div>
        <div class="chat-item-preview">{{ chat.last_message?.text || 'Нет сообщений' }}</div>
        <span v-if="chat.unread_count > 0" class="unread-badge">{{ formatUnread(chat.unread_count) }}</span>
      </div>
      <div v-if="chatStore.chats.length === 0" style="padding:1rem;color:#999;text-align:center">
        Нет чатов
      </div>
    </div>
    <button class="new-chat-btn" @click="showModal = true">+ Новый чат</button>
    <NewChatModal :is-open="showModal" @close="showModal = false" />
  </div>
</template>