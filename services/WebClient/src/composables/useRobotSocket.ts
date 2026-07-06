import { readonly, ref } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''

export type SocketStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting' | 'error'
export type RobotState = Record<string, unknown>
export type RobotAvailability = 'robot_disponible' | 'robot_desconectado_reconectando' | 'robot_no_disponible'

interface RobotResponseJSONRPC {
  "jsonrpc": string,
  "method": string,
  "params": Record<string, unknown> | null
}

const isJSONRPC = (data: unknown): data is RobotResponseJSONRPC => {
  if (typeof data !== 'object' || data === null) return false
  return data.hasOwnProperty('jsonrpc')
}

const HEARTBEAT_WATCHDOG_INTERVAL_MS = 1000
const HEARTBEAT_TIMEOUT_MS = 25000
const MIN_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

export function useRobotSocket() {
  const status = ref<SocketStatus>('disconnected')
  const robotStatus = ref<RobotAvailability>('robot_disponible')
  const messages = ref<Record<string, unknown>[]>([])
  const error = ref<string | null>(null)
  const robotState = ref<RobotState>({})

  let ws: WebSocket | null = null
  let robotId: string | null = null
  let robotAccessToken: string | null = null
  let manualDisconnect = false
  let authFailed = false
  let reconnectDelayMs = MIN_RECONNECT_DELAY_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let heartbeatWatchdogTimer: ReturnType<typeof setInterval> | null = null
  let lastPingAt = Date.now()

  function clearTimers() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatWatchdogTimer !== null) {
      clearInterval(heartbeatWatchdogTimer)
      heartbeatWatchdogTimer = null
    }
  }

  function scheduleReconnect() {
    if (manualDisconnect || authFailed || reconnectTimer !== null) return
    status.value = 'reconnecting'
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (robotId && robotAccessToken) connect(robotId, robotAccessToken)
    }, reconnectDelayMs)
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS)
  }

  function startHeartbeatWatchdog() {
    lastPingAt = Date.now()
    heartbeatWatchdogTimer = setInterval(() => {
      if (Date.now() - lastPingAt > HEARTBEAT_TIMEOUT_MS) {
        ws?.close()
      }
    }, HEARTBEAT_WATCHDOG_INTERVAL_MS)
  }

  function connect(_robotId: string, _robotAccessToken: string) {
    manualDisconnect = false
    authFailed = false
    robotId = _robotId
    robotAccessToken = _robotAccessToken
    status.value = 'connecting'
    error.value = null

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}${WS_BASE}/user/robot/send_command`

    ws = new WebSocket(wsUrl)

    ws.onopen = () => {
      status.value = 'authenticating'
      ws!.send(JSON.stringify({ token: robotAccessToken, robot_id: robotId }))
    }

    ws.onmessage = async (event: MessageEvent) => {
      const data = JSON.parse(
        event.data instanceof Blob
        ? await event.data.text()
        : event.data
      )

      if (data && data.type === 'ping') {
        lastPingAt = Date.now()
        ws?.send(JSON.stringify({ type: 'pong' }))
        return
      }

      if (status.value === 'authenticating') {
        if (data.message === 'success auth') {
          status.value = 'connected'
          robotStatus.value = 'robot_disponible'
          reconnectDelayMs = MIN_RECONNECT_DELAY_MS
          startHeartbeatWatchdog()
        } else {
          status.value = 'error'
          error.value = data.message || 'Error de autenticación'
          authFailed = true
        }
        return
      }

      if (data && typeof data.status === 'string' && data.status.startsWith('robot_')) {
        robotStatus.value = data.status as RobotAvailability
        return
      }

      if (messages.value.length > 5) {
        messages.value.shift()
      }

      messages.value.push(data)

      if (isJSONRPC(data) && data.method === "status.update") {
        robotState.value = data.params as RobotState
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      error.value = 'Error de conexión WebSocket'
    }

    ws.onclose = () => {
      clearTimers()
      if (manualDisconnect) {
        status.value = 'disconnected'
        return
      }
      if (authFailed) {
        status.value = 'error'
        return
      }
      scheduleReconnect()
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
    manualDisconnect = true
    clearTimers()
    if (ws) {
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
  }

  function clearMessagesHistory() {
    messages.value = []
  }

  return {
    status: readonly(status),
    robotStatus: readonly(robotStatus),
    messages: readonly(messages),
    robotState: readonly(robotState),
    error,
    connect,
    sendCommand,
    disconnect,
    clearMessagesHistory
  }
}
