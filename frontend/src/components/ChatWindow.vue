<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useChatSocket } from '../composables/useChatSocket'
import MessageBubble from './MessageBubble.vue'
import api from '../services/api'

const auth = useAuthStore()
const chatStore = useChatStore()
const inputText = ref('')
const messagesEnd = ref<HTMLElement>()

// WebSocket подключение
const { status: wsStatus, sendMessage: sendWs } = useChatSocket(
  () => chatStore.selectedChatId,
  () => localStorage.getItem('access_token'),
  {
    onMessage: (msg) => chatStore.addMessage(msg),
    onUserStatus: (userId, status) => console.log(`[WS] ${userId}: ${status}`),
    onMessagesRead: () => chatStore.markAllRead(auth.user?.id || ''),
  },
)

// Автоскролл при новых сообщениях
watch(() => chatStore.messages.length, async () => {
  await nextTick()
  messagesEnd.value?.scrollIntoView({ behavior: 'smooth' })
})

const currentChatName = computed(() => {
  const chat = chatStore.chats.find((c) => c.id === chatStore.selectedChatId)
  if (!chat) return ''
  if (chat.name) return chat.name
  if (chat.interlocutor) return chat.interlocutor.first_name || chat.interlocutor.phone
  return 'Чат'
})

const statusColor = computed(() => ({
  connected: '#4caf50', connecting: '#ff9800', disconnected: '#e74c3c', error: '#e74c3c',
}[wsStatus.value]))

const statusLabel = computed(() => ({
  connected: 'online', connecting: 'подключение...', disconnected: 'offline', error: 'offline',
}[wsStatus.value]))

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !chatStore.selectedChatId) return
  inputText.value = ''

  const sent = sendWs(text)
  if (!sent) {
    try {
      const { data } = await api.post(`/chats/${chatStore.selectedChatId}/send/`, { text })
      chatStore.addMessage(data)
    } catch (e) { console.error('Send failed:', e) }
  }
}
</script>

<template>
  <div class="chat-area">
    <template v-if="chatStore.selectedChatId">
      <div class="chat-header">
        {{ currentChatName }}
        <span class="ws-indicator">
          <span class="ws-dot" :style="{ background: statusColor }" />
          {{ statusLabel }}
        </span>
      </div>
      <div class="messages-container">
        <MessageBubble
          v-for="msg in chatStore.messages"
          :key="msg.id"
          :message="msg"
          :is-mine="msg.sender.id === auth.user?.id"
        />
        <div ref="messagesEnd" />
      </div>
      <div class="input-area">
        <input
          v-model="inputText"
          placeholder="Сообщение..."
          @keyup.enter="handleSend"
        />
        <button :disabled="!inputText.trim()" @click="handleSend">→</button>
      </div>
    </template>
    <div v-else class="empty-state">Выберите чат или создайте новый</div>
  </div>
</template>