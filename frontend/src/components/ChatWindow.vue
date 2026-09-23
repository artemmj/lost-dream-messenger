<script setup lang="ts">
import { ref, nextTick, watch, computed } from 'vue'
import { onKeyStroke } from '@vueuse/core'
import { useAuthStore } from '../stores/auth'
import { useChatStore } from '../stores/chat'
import { useChatSocket } from '../composables/useChatSocket'
import MessageBubble from './MessageBubble.vue'
import GroupMembersModal from './GroupMembersModal.vue'
import api from '../services/api'

const auth = useAuthStore()
const chatStore = useChatStore()
const inputText = ref('')
const messagesContainer = ref<HTMLElement>()
const showMembers = ref(false)
// Плашка вместо окна чата, когда сервер закрыл сокет
const closedNotice = ref('')
// Сервер отклонил событие, сокет при этом жив (пустой текст, анти-флуд)
const sendError = ref('')

const CLOSE_NOTICES: Record<number, string> = {
  4003: 'Вы удалены из этого чата',
  4004: 'Чат удалён',
  4029: 'Real-time отключено: слишком много попыток переподключения. Обновите страницу через минуту.',
  4009: 'Real-time отключено: слишком много открытых вкладок. Закройте лишние и обновите страницу.',
}
// Убираем чат из списка только когда мы перестали быть участником. При WS-лимитах
// участник остаётся в чате — иначе лимитер выглядел бы как удаление чата.
const FORGET_CHAT_CODES = [4003, 4004]

// WebSocket подключение
const { status: wsStatus, sendMessage: sendWs } = useChatSocket(
  () => chatStore.selectedChatId,
  () => localStorage.getItem('access_token'),
  {
    onMessage: (msg) => chatStore.addMessage(msg),
    onUserStatus: (userId, status) => chatStore.setUserStatus(userId, status),
    // Событие приходит и самому читателю — игнорируем собственное, иначе свои
    // сообщения локально помечаются прочитанными, хотя собеседник их не читал
    onMessagesRead: (readerId) => {
      if (readerId !== auth.user?.id) chatStore.markAllRead(auth.user?.id || '')
    },
    onInitialPresence: (userIds) => chatStore.setInitialPresence(userIds),
    // Пока сокет был разорван, сообщения приходили мимо нас — добираем их через REST.
    // Прокрутку вниз возьмёт на себя watcher по lastMessageId.
    onReconnect: () => {
      chatStore.reloadMessages()
      chatStore.loadChats()
    },
    onError: (message) => {
      sendError.value = message
    },
    onClose: (code) => {
      const notice = CLOSE_NOTICES[code]
      if (!notice || !chatStore.selectedChatId) return
      closedNotice.value = notice
      if (FORGET_CHAT_CODES.includes(code)) {
        chatStore.removeChat(chatStore.selectedChatId)
      }
    },
  },
)

// Индикатор соединения живёт в сайдбаре — пробрасываем статус в store
watch(wsStatus, (s) => chatStore.setWsStatus(s), { immediate: true })

// Esc закрывает верхний слой: открытая модалка перехватывает Esc сама, а чат трогать
// не надо. Состояние модалок живёт в соседних компонентах, поэтому смотрим на оверлей.
onKeyStroke('Escape', () => {
  if (document.querySelector('.modal-overlay')) return
  chatStore.closeChat()
})

// true = только что открыли чат: первая прокрутка мгновенная (без анимации),
// иначе smooth-анимация с scrollTop=0 сама провоцирует догрузку истории
let isChatSwitch = true
// Направление прокрутки: историю грузим только при пользовательском скролле вверх
let lastScrollTop = 0

watch(() => chatStore.selectedChatId, () => {
  closedNotice.value = ''
  sendError.value = ''
  isChatSwitch = true
  lastScrollTop = 0
})

// Автоскролл — только когда меняется последнее сообщение (новые сообщения),
// чтобы догрузка истории сверху не сбрасывала позицию
const lastMessageId = computed(
  () => chatStore.messages[chatStore.messages.length - 1]?.id,
)

watch(lastMessageId, async (id) => {
  if (!id) return
  await nextTick()
  const el = messagesContainer.value
  if (!el) return
  if (isChatSwitch) {
    isChatSwitch = false
    // Если первая страница не заполняет контейнер — догрузить старую нечем
    // (скролл не появится), поэтому добираем страницы, пока не появится скролл
    while (
      el.scrollHeight <= el.clientHeight &&
      chatStore.hasMoreMessages &&
      !chatStore.isLoadingHistory
    ) {
      await chatStore.loadOlderMessages()
      await nextTick()
    }
    el.scrollTop = el.scrollHeight
    lastScrollTop = el.scrollTop
  } else {
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }
})

// Infinite scroll вверх: догрузка старых сообщений с якорем позиции.
// Срабатывает только при прокрутке ВВЕРХ у верхушки — программные
// прокрутки вниз (автоскролл) направление не проходят и игнорируются.
async function handleScroll() {
  const el = messagesContainer.value
  if (!el || chatStore.isLoadingHistory) return
  const prevTop = lastScrollTop
  lastScrollTop = el.scrollTop
  if (el.scrollTop >= 100 || el.scrollTop >= prevTop || !chatStore.hasMoreMessages) return

  const prevHeight = el.scrollHeight
  await chatStore.loadOlderMessages()
  await nextTick()
  el.scrollTop = prevTop + (el.scrollHeight - prevHeight)
  lastScrollTop = el.scrollTop
}

const selectedChat = computed(() =>
  chatStore.chats.find((c) => c.id === chatStore.selectedChatId),
)

const currentChatName = computed(() => {
  const chat = selectedChat.value
  if (!chat) return ''
  if (chat.name) return chat.name
  if (chat.interlocutor) return chat.interlocutor.first_name || chat.interlocutor.phone
  return 'Чат'
})

const isGroup = computed(() => selectedChat.value?.type === 'GROUP')

/** Онлайн-статус собеседника (только для личных чатов) */
const interlocutorOnline = computed(() => {
  const chat = selectedChat.value
  if (!chat || chat.type !== 'PRIVATE' || !chat.interlocutor) return null
  return chatStore.onlineUsers.has(chat.interlocutor.id)
})

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || !chatStore.selectedChatId) return
  inputText.value = ''
  sendError.value = ''

  const sent = sendWs(text)
  if (!sent) {
    try {
      const { data } = await api.post(`/chats/${chatStore.selectedChatId}/send/`, { text })
      chatStore.addMessage(data)
    } catch (e: any) {
      console.error('Send failed:', e)
      inputText.value = text
      // Здесь же прилетает и 429 от REST-scope `send`
      sendError.value = e.response?.data?.detail || 'Не отправлено, попробуйте ещё раз'
    }
  }
}
</script>

<template>
  <div class="chat-area">
    <template v-if="chatStore.selectedChatId">
      <div class="chat-header">
        <div class="chat-header-info">
          <div class="chat-header-name">{{ currentChatName }}</div>
          <div v-if="interlocutorOnline !== null" class="presence-label">
            <span
              class="ws-dot"
              :style="{ background: interlocutorOnline ? 'var(--color-success)' : '#bbb' }"
            />
            {{ interlocutorOnline ? 'в сети' : 'не в сети' }}
          </div>
        </div>
        <button v-if="isGroup" class="members-btn" @click="showMembers = true">
          Участники{{ chatStore.currentChatDetails ? ` (${chatStore.currentChatDetails.members.length})` : '' }}
        </button>
        <button class="chat-close-btn" title="Закрыть чат (Esc)" @click="chatStore.closeChat()">
          ×
        </button>
      </div>
      <!-- При WS-лимитах чат остаётся выбранным — плашка показывается внутри окна -->
      <div v-if="closedNotice" class="connection-notice">{{ closedNotice }}</div>
      <div ref="messagesContainer" class="messages-container" @scroll="handleScroll">
        <div v-if="chatStore.isLoadingHistory" class="history-loading">Загрузка истории...</div>
        <MessageBubble
          v-for="msg in chatStore.messages"
          :key="msg.id"
          :message="msg"
          :is-mine="msg.sender.id === auth.user?.id"
        />
      </div>
      <div v-if="sendError" class="send-error">{{ sendError }}</div>
      <div class="input-area">
        <input
          v-model="inputText"
          placeholder="Сообщение..."
          @keyup.enter="handleSend"
        />
        <button :disabled="!inputText.trim()" @click="handleSend">→</button>
      </div>
    </template>
    <div v-else-if="closedNotice" class="empty-state">{{ closedNotice }}</div>
    <div v-else class="empty-state">Выберите чат или создайте новый</div>

    <GroupMembersModal :is-open="showMembers" @close="showMembers = false" />
  </div>
</template>
