import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../services/api'

export interface User {
  id: string
  phone: string
  email?: string
  first_name?: string
  last_name?: string
}

export interface ChatMember extends User {
  is_admin: boolean
}

export interface Message {
  id: string
  chat: string
  sender: User
  text: string
  created_at: string
  is_read: boolean
}

export interface ChatListItem {
  id: string
  type: 'PRIVATE' | 'GROUP'
  name: string
  created_at: string
  last_message: Message | null
  interlocutor: User | null
}

export interface ChatDetails {
  id: string
  type: 'PRIVATE' | 'GROUP'
  name: string
  members: ChatMember[]
  my_is_admin: boolean
  created_at: string
}

export type WsStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export const useChatStore = defineStore('chat', () => {
  const chats = ref<ChatListItem[]>([])
  const selectedChatId = ref<string | null>(null)
  const messages = ref<Message[]>([])
  const currentChatDetails = ref<ChatDetails | null>(null)

  // Состояние WS-соединения текущего чата: пишет ChatWindow, читает ChatSidebar
  const wsStatus = ref<WsStatus>('disconnected')

  // Пагинация истории: страница 1 = последние сообщения, страница N = более старые
  const messagesPage = ref(1)
  const hasMoreMessages = ref(false)
  const isLoadingHistory = ref(false)

  // Присутствие: id пользователей, которые сейчас онлайн
  const onlineUsers = ref<Set<string>>(new Set())

  async function loadChats() {
    try {
      const { data } = await api.get('/chats/')
      chats.value = Array.isArray(data) ? data : data.results
    } catch (e) {
      console.error('loadChats:', e)
    }
  }

  async function selectChat(chatId: string) {
    selectedChatId.value = chatId
    messages.value = []
    messagesPage.value = 1
    hasMoreMessages.value = false
    currentChatDetails.value = null
    try {
      const { data } = await api.get(`/chats/${chatId}/messages/`)
      if (selectedChatId.value !== chatId) return
      messages.value = Array.isArray(data) ? data : data.results
      hasMoreMessages.value = Array.isArray(data) ? false : !!data.next
    } catch (e) {
      console.error('loadMessages:', e)
    }
    loadChatDetails(chatId)
  }

  async function loadChatDetails(chatId: string) {
    try {
      const { data } = await api.get(`/chats/${chatId}/`)
      if (selectedChatId.value === chatId) currentChatDetails.value = data
    } catch (e) {
      console.error('loadChatDetails:', e)
    }
  }

  /** Догрузка более старых сообщений (prepend с сохранением порядка) */
  async function loadOlderMessages() {
    const chatId = selectedChatId.value
    if (!chatId || isLoadingHistory.value || !hasMoreMessages.value) return
    isLoadingHistory.value = true
    try {
      const nextPage = messagesPage.value + 1
      const { data } = await api.get(`/chats/${chatId}/messages/`, {
        params: { page: nextPage },
      })
      if (selectedChatId.value !== chatId) return
      const older: Message[] = data.results ?? []
      const existing = new Set(messages.value.map((m) => m.id))
      messages.value = [...older.filter((m) => !existing.has(m.id)), ...messages.value]
      messagesPage.value = nextPage
      hasMoreMessages.value = !!data.next
    } catch (e) {
      console.error('loadOlderMessages:', e)
    } finally {
      isLoadingHistory.value = false
    }
  }

  /** Добавляем сообщение от WS или REST (с дедупликацией) */
  function addMessage(msg: Message) {
    if (!messages.value.some((m) => m.id === msg.id)) {
      messages.value.push(msg)
    }
    // Обновляем превью в sidebar
    const chat = chats.value.find((c) => c.id === msg.chat)
    if (chat) chat.last_message = msg
  }

  /** Помечаем все свои сообщения как прочитанные */
  function markAllRead(myUserId: string) {
    messages.value = messages.value.map((m) =>
      m.sender.id === myUserId && !m.is_read ? { ...m, is_read: true } : m,
    )
  }

  function removeChat(chatId: string) {
    chats.value = chats.value.filter((c) => c.id !== chatId)
    if (selectedChatId.value === chatId) {
      selectedChatId.value = null
      messages.value = []
      currentChatDetails.value = null
    }
  }

  function setUserStatus(userId: string, status: string) {
    if (status === 'online') onlineUsers.value.add(userId)
    else onlineUsers.value.delete(userId)
  }

  function setInitialPresence(userIds: string[]) {
    onlineUsers.value = new Set(userIds)
  }

  function setWsStatus(status: WsStatus) {
    wsStatus.value = status
  }

  function resetMessages() {
    messages.value = []
    selectedChatId.value = null
    currentChatDetails.value = null
    wsStatus.value = 'disconnected'
  }

  return {
    chats,
    selectedChatId,
    messages,
    currentChatDetails,
    messagesPage,
    hasMoreMessages,
    isLoadingHistory,
    onlineUsers,
    wsStatus,
    loadChats,
    selectChat,
    loadChatDetails,
    loadOlderMessages,
    addMessage,
    markAllRead,
    removeChat,
    setUserStatus,
    setInitialPresence,
    setWsStatus,
    resetMessages,
  }
})
