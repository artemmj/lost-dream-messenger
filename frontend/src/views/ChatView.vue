<script setup lang="ts">
import { onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import ChatSidebar from '../components/ChatSidebar.vue'
import ChatWindow from '../components/ChatWindow.vue'

const chatStore = useChatStore()
onMounted(() => chatStore.loadChats())
</script>

<template>
  <div class="chat-layout">
    <ChatSidebar />
    <ChatWindow />
  </div>
</template>
