// src/composables/useNotificationsSocket.ts
import { onMounted, onUnmounted } from 'vue'
import type { Message } from '../stores/chat'
import { NO_RECONNECT_CODES } from './useChatSocket'

export interface NotificationEvents {
  onNewMessage: (message: Message, unreadCount: number) => void
  onChatRead: (chatId: string) => void
  onChatDeleted: (chatId: string) => void
  onChatRenamed: (chatId: string, name: string) => void
  onMemberRemoved: (chatId: string) => void
}

/**
 * Личный WebSocket-канал пользователя: ws/notifications/?token=<jwt>.
 *
 * Сокет чата живёт, пока чат открыт, поэтому уведомление в другой чат доставить
 * не через что. Здесь приходят события по всем чатам сразу, и здесь же сервер
 * считает непрочитанное — клиенту не нужен свой курсор.
 */
export function useNotificationsSocket(
  token: () => string | null,
  events: NotificationEvents,
) {
  let ws: WebSocket | null = null
  let reconnectTimer: number | undefined

  function connect() {
    const t = token()
    if (!t || ws) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${location.host}/ws/notifications/?token=${t}`)
    ws = socket

    socket.onmessage = (event) => {
      if (ws !== socket) return
      try {
        const data = JSON.parse(event.data)
        switch (data.type) {
          case 'new_message':
            events.onNewMessage(data.message as Message, data.unread_count ?? 1)
            break
          case 'chat_read':
            events.onChatRead(data.chat)
            break
          case 'chat_deleted':
            events.onChatDeleted(data.chat)
            break
          case 'chat_renamed':
            events.onChatRenamed(data.chat, data.name)
            break
          case 'member_removed':
            events.onMemberRemoved(data.chat)
            break
        }
      } catch (e) {
        console.error('[notifications WS] Parse error:', e)
      }
    }

    socket.onclose = (event) => {
      // События уже закрытого сокета не должны влиять на новое соединение
      if (ws !== socket) return
      ws = null
      // 4001 — невалидный JWT, 4009/4029 — лимиты подключений: переподключение
      // только продлит бан. Поднимем канал, когда вкладка снова станет видимой.
      if (NO_RECONNECT_CODES.includes(event.code)) return
      reconnectTimer = window.setTimeout(connect, 2000)
    }

    socket.onerror = () => {
      // За ошибкой всегда следует close — перезапуск делается там
    }
  }

  function handleVisibility() {
    if (document.visibilityState !== 'visible') return
    // После сна, обрыва или истёкшего токена (4001) поднимаем канал с актуальным JWT
    if (!ws) connect()
  }

  onMounted(() => {
    connect()
    document.addEventListener('visibilitychange', handleVisibility)
  })

  onUnmounted(() => {
    document.removeEventListener('visibilitychange', handleVisibility)
    if (reconnectTimer) window.clearTimeout(reconnectTimer)
    if (ws) {
      ws.close(1000, 'Client disconnect')
      ws = null
    }
  })
}
