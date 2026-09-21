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

export const useChatStore = defineStore('chat', () => {
  const chats = ref<ChatListItem[]>([])
  const selectedChatId = ref<string | null>(null)
  const messages = ref<Message[]>([])

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
    try {
      const { data } = await api.get(`/chats/${chatId}/messages/`)
      messages.value = Array.isArray(data) ? data : data.results
    } catch (e) {
      console.error('loadMessages:', e)
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

  function resetMessages() {
    messages.value = []
    selectedChatId.value = null
  }

  return { chats, selectedChatId, messages, loadChats, selectChat, addMessage, markAllRead, resetMessages }
})