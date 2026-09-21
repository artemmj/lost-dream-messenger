<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import NewChatModal from './NewChatModal.vue'

const auth = useAuthStore()
const chatStore = useChatStore()
const router = useRouter()
const showModal = ref(false)

function handleLogout() {
  chatStore.resetMessages()
  auth.logout()
  router.push('/login')
}

function getChatName(chat: any): string {
  if (chat.name) return chat.name
  if (chat.interlocutor) return chat.interlocutor.first_name || chat.interlocutor.phone
  return chat.type === 'GROUP' ? 'Групповой чат' : 'Личный чат'
}
</script>

<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <span>{{ auth.user?.phone }}</span>
      <button class="logout-btn" @click="handleLogout">Выйти</button>
    </div>
    <div class="chat-list">
      <div
        v-for="chat in chatStore.chats"
        :key="chat.id"
        class="chat-item"
        :class="{ active: chatStore.selectedChatId === chat.id }"
        @click="chatStore.selectChat(chat.id)"
      >
        <div class="chat-item-name">{{ getChatName(chat) }}</div>
        <div class="chat-item-preview">{{ chat.last_message?.text || 'Нет сообщений' }}</div>
      </div>
      <div v-if="chatStore.chats.length === 0" style="padding:1rem;color:#999;text-align:center">
        Нет чатов
      </div>
    </div>
    <button class="new-chat-btn" @click="showModal = true">+ Новый чат</button>
    <NewChatModal :is-open="showModal" @close="showModal = false" />
  </div>
</template>