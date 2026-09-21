<script setup lang="ts">
import type { Message } from '../stores/chat'

defineProps<{
  message: Message
  isMine: boolean
}>()

const formatTime = (iso: string) =>
  new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
</script>

<template>
  <div class="msg" :class="isMine ? 'mine' : 'theirs'">
    <div v-if="!isMine" class="msg-sender">
      {{ message.sender.first_name || message.sender.phone }}
    </div>
    {{ message.text }}
    <div class="msg-meta">
      {{ formatTime(message.created_at) }}
      <span v-if="isMine" class="msg-read" :style="{ color: message.is_read ? '#4caf50' : '#bbb' }">
        {{ message.is_read ? '✓✓' : '✓' }}
      </span>
    </div>
  </div>
</template>