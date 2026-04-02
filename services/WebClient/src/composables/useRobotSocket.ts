import { ref } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''

export type SocketStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'error'

export function useRobotSocket() {
  const status = ref<SocketStatus>('disconnected')
  const messages = ref<Record<string, unknown>[]>([])
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let robotId: string | null = null
  let robotAccessToken: string | null = null

  function connect(authToken: string, _robotId: string, _robotAccessToken: string) {
    robotId = _robotId
    robotAccessToken = _robotAccessToken
    status.value = 'connecting'
    error.value = null

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}${WS_BASE}/user/robot/send_command`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      status.value = 'authenticating'
      ws!.send(JSON.stringify({ token: authToken, robot_id: robotId }))
    }

    ws.onmessage = async (event: MessageEvent) => {
      const data = JSON.parse(
        event.data instanceof Blob
        ? await event.data.text()
        : event.data
      )

      if (status.value === 'authenticating') {
        if (data.message === 'success auth') {
          status.value = 'connected'
        } else {
          status.value = 'error'
          error.value = data.message || 'Error de autenticación'
        }
        return
      }

      messages.value.push(data)
    }

    ws.onerror = () => {
      status.value = 'error'
      error.value = 'Error de conexión WebSocket'
    }

    ws.onclose = () => {
      if (status.value !== 'error') {
        status.value = 'disconnected'
      }
    }
  }

  function sendCommand(method: string) {
    if (!ws || status.value !== 'connected') return

    ws.send(JSON.stringify({
      method,
      access_token: robotAccessToken,
      robot_id: robotId,
    }))
  }

  function disconnect() {
    if (ws) {
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
  }

  return { status, messages, error, connect, sendCommand, disconnect }
}
