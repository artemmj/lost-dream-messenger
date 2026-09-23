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
  unread_count: number
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

// PAGE_SIZE бэкенда: полная страница означает, что пропущенных сообщений может быть больше
const MESSAGES_PAGE_SIZE = 50

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
    // Присутствие относится к конкретному чату: без сброса до initial_presence
    // показывали бы статусы участников предыдущего чата
    onlineUsers.value = new Set()
    try {
      const { data } = await api.get(`/chats/${chatId}/messages/`)
      if (selectedChatId.value !== chatId) return
      messages.value = Array.isArray(data) ? data : data.results
      hasMoreMessages.value = Array.isArray(data) ? false : !!data.next
    } catch (e) {
      console.error('loadMessages:', e)
    }
    loadChatDetails(chatId)
    markRead(chatId)
  }

  /** Сдвигаем курсор прочтения на сервере и убираем бейдж. */
  async function markRead(chatId: string) {
    try {
      await api.post(`/chats/${chatId}/read/`)
      setUnread(chatId, 0)
    } catch (e) {
      console.error('markRead:', e)
    }
  }

  /**
   * Бейдж непрочитанного. Чата может не быть в списке — например нас только что
   * добавили в группу: тогда перечитываем список, счётчик придёт с ним.
   */
  function setUnread(chatId: string, count: number) {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) {
      loadChats()
      return
    }
    chat.unread_count = count
  }

  /**
   * Уведомление из личного канала: обновляем превью и счётчик.
   * Если этот чат открыт на видимой вкладке, сообщение уже прочитано — тут же
   * подтверждаем это серверу (он разнесёт chat_read по остальным вкладкам).
   */
  function applyNewMessage(message: Message, unreadCount: number) {
    const chatId = message.chat
    if (chatId === selectedChatId.value && document.visibilityState === 'visible') {
      markRead(chatId)
    } else {
      setUnread(chatId, unreadCount)
    }
    const chat = chats.value.find((c) => c.id === chatId)
    if (chat) chat.last_message = message
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

  /**
   * Перечитывание истории после WS-reconnect: добираем сообщения, пришедшие,
   * пока соединение было разорвано.
   */
  async function reloadMessages() {
    const chatId = selectedChatId.value
    if (!chatId) return
    try {
      const { data } = await api.get(`/chats/${chatId}/messages/`)
      if (selectedChatId.value !== chatId) return
      const latest: Message[] = Array.isArray(data) ? data : data.results ?? []
      if (latest.length >= MESSAGES_PAGE_SIZE) {
        // Пока нас не было, пришло не меньше целой страницы — в истории могла
        // появиться «дыра», поэтому перезагружаем её с конца.
        messages.value = latest
        messagesPage.value = 1
        hasMoreMessages.value = Array.isArray(data) ? false : !!data.next
        return
      }
      const known = new Map(messages.value.map((m) => [m.id, m]))
      const fresh: Message[] = []
      for (const msg of latest) {
        const prev = known.get(msg.id)
        // Статус прочтения мог измениться, пока сокет был закрыт
        if (prev) prev.is_read = msg.is_read
        else fresh.push(msg)
      }
      if (fresh.length) messages.value = [...messages.value, ...fresh]
    } catch (e) {
      console.error('reloadMessages:', e)
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

  /**
   * Новое название чата — из ответа PATCH или из личного канала (`chat_renamed`).
   * Заголовок открытого чата берётся из элемента списка, поэтому его обновляем
   * сразу; детали перечитывать нечем — там название тоже есть, но оно не влияет
   * на права.
   */
  function applyRename(chatId: string, name: string) {
    const chat = chats.value.find((c) => c.id === chatId)
    if (!chat) {
      // Чата в списке нет — он мог прийти, пока мы его не видели: перечитаем
      loadChats()
      return
    }
    chat.name = name
    if (currentChatDetails.value?.id === chatId) currentChatDetails.value.name = name
  }

  /** Переименование GROUP-чата (только админ — иначе 403). Ошибку не глотаем. */
  async function renameChat(chatId: string, name: string) {
    const { data } = await api.patch(`/chats/${chatId}/`, { name })
    applyRename(chatId, data?.name ?? name)
  }

  /**
   * Удаление чата вместе с сообщениями. GROUP — только админ (иначе 403),
   * PRIVATE — любой участник. Ошибку не глотаем: текст detail нужен кнопке.
   * Сервер сам разнесёт chat.deleted участникам, но список обновляем сразу,
   * не дожидаясь WS.
   */
  async function deleteChat(chatId: string) {
    await api.delete(`/chats/${chatId}/`)
    removeChat(chatId)
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

  /**
   * Закрыть текущий чат: снимает выделение и выгружает окно, но не трогает список
   * (в отличие от removeChat — там чат перестал существовать для нас).
   * WS закрывается сам: useChatSocket следит за selectedChatId.
   */
  function closeChat() {
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
    markRead,
    setUnread,
    applyNewMessage,
    loadChatDetails,
    loadOlderMessages,
    reloadMessages,
    addMessage,
    markAllRead,
    removeChat,
    applyRename,
    renameChat,
    deleteChat,
    setUserStatus,
    setInitialPresence,
    setWsStatus,
    closeChat,
  }
})
