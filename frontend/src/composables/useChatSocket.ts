// src/composables/useChatSocket.ts
import { ref, watch, onUnmounted } from 'vue'
import type { Message, WsStatus } from '../stores/chat'

interface WsCallbacks {
  onMessage: (msg: Message) => void
  onUserStatus: (userId: string, status: string) => void
  onMessagesRead: (readerId: string) => void
  onInitialPresence: (userIds: string[]) => void
  onClose?: (code: number) => void
}

/**
 * Composable для WebSocket-подключения к чату.
 *
 * Использование:
 *   const { status, sendMessage } = useChatSocket(chatId, token, callbacks)
 *
 * Автоматически подключается при изменении chatId,
 * отключается при unmount компонента.
 */
export function useChatSocket(
  chatId: () => string | null,
  token: () => string | null,
  callbacks: WsCallbacks,
) {
  const status = ref<WsStatus>('disconnected')
  let ws: WebSocket | null = null

  function connect(id: string) {
    if (ws) ws.close()
    const t = token()
    if (!t) return

    status.value = 'connecting'
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws = new WebSocket(`${protocol}//${location.host}/ws/chat/${id}/?token=${t}`)

    ws.onopen = () => { status.value = 'connected' }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.type === 'user_status') {
          callbacks.onUserStatus(data.user_id, data.status)
        } else if (data.type === 'messages_read') {
          callbacks.onMessagesRead(data.reader_id)
        } else if (data.type === 'initial_presence') {
          callbacks.onInitialPresence(data.user_ids ?? [])
        } else if (data.id) {
          callbacks.onMessage(data as Message)
        }
      } catch (e) {
        console.error('[WS] Parse error:', e)
      }
    }

    ws.onclose = (event) => {
      status.value = 'disconnected'
      callbacks.onClose?.(event.code)
      // Авто-reconnect кроме случаев отказа в авторизации/доступе
      if (![4001, 4003].includes(event.code)) {
        setTimeout(() => {
          if (chatId() === id) connect(id)
        }, 2000)
      }
    }

    ws.onerror = () => { status.value = 'error' }
  }

  function disconnect() {
    if (ws) { ws.close(1000, 'Client disconnect'); ws = null }
    status.value = 'disconnected'
  }

  function sendMessage(text: string): boolean {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ text }))
      return true
    }
    return false
  }

  // Следим за изменением chatId — переподключаемся
  watch(chatId, (newId) => {
    if (newId) connect(newId)
    else disconnect()
  }, { immediate: true })

  // Cleanup при unmount
  onUnmounted(disconnect)

  return { status, sendMessage }
}
