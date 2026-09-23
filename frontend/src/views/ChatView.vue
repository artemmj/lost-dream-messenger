<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useChatStore } from '../stores/chat'
import { useNotificationsSocket } from '../composables/useNotificationsSocket'
import ChatSidebar from '../components/ChatSidebar.vue'
import ChatWindow from '../components/ChatWindow.vue'

const chatStore = useChatStore()

onMounted(() => chatStore.loadChats())

// Личный канал: уведомления по всем чатам, а не только по открытому
useNotificationsSocket(() => localStorage.getItem('access_token'), {
  onNewMessage: (message, unreadCount) =>
    chatStore.applyNewMessage(message, unreadCount),
  onChatRead: (chatId) => chatStore.setUnread(chatId, 0),
  onChatDeleted: (chatId) => chatStore.removeChat(chatId),
  onMemberRemoved: (chatId) => chatStore.removeChat(chatId),
})

// Вернулись во вкладку с открытым чатом — всё, что пришло в отсутствие
// пользователя, считается прочитанным
function handleVisibility() {
  if (document.visibilityState === 'visible' && chatStore.selectedChatId) {
    chatStore.markRead(chatStore.selectedChatId)
  }
}

onMounted(() => document.addEventListener('visibilitychange', handleVisibility))
onUnmounted(() => document.removeEventListener('visibilitychange', handleVisibility))
</script>

<template>
  <div class="chat-layout">
    <ChatSidebar />
    <ChatWindow />
  </div>
</template>
