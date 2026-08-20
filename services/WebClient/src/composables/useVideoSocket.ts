import { readonly, ref } from 'vue'

const WS_BASE = import.meta.env.VITE_WS_BASE || ''

export type VideoStatus = 'disconnected' | 'connecting' | 'authenticating' | 'connected' | 'reconnecting' | 'error'

const MIN_RECONNECT_DELAY_MS = 1000
const MAX_RECONNECT_DELAY_MS = 30000

export function useVideoSocket() {
  const status = ref<VideoStatus>('disconnected')
  const error = ref<string | null>(null)

  let ws: WebSocket | null = null
  let canvasCtx: CanvasRenderingContext2D | null = null
  let robotId: string | null = null
  let robotAccessToken: string | null = null
  let manualDisconnect = false
  let authFailed = false
  let reconnectDelayMs = MIN_RECONNECT_DELAY_MS
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let painting = false

  function scheduleReconnect() {
    if (manualDisconnect || authFailed || reconnectTimer !== null) return
    status.value = 'reconnecting'
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      if (robotId && robotAccessToken && canvasCtx) connect(robotId, robotAccessToken, canvasCtx)
    }, reconnectDelayMs)
    reconnectDelayMs = Math.min(reconnectDelayMs * 2, MAX_RECONNECT_DELAY_MS)
  }

  async function paintFrame(blob: Blob) {
    // Descarta el frame si todavía se está pintando el anterior — mismo
    // criterio "último frame gana" que el resto del canal de video.
    if (painting || !canvasCtx) return
    painting = true
    try {
      const bitmap = await createImageBitmap(blob)
      canvasCtx.canvas.width = bitmap.width
      canvasCtx.canvas.height = bitmap.height
      canvasCtx.drawImage(bitmap, 0, 0)
      bitmap.close()
    } finally {
      painting = false
    }
  }

  function connect(_robotId: string, _robotAccessToken: string, ctx: CanvasRenderingContext2D) {
    manualDisconnect = false
    authFailed = false
    robotId = _robotId
    robotAccessToken = _robotAccessToken
    canvasCtx = ctx
    status.value = 'connecting'
    error.value = null

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${location.host}${WS_BASE}/user/robot/video`

    ws = new WebSocket(wsUrl)
    ws.binaryType = 'blob'

    ws.onopen = () => {
      status.value = 'authenticating'
      ws!.send(JSON.stringify({ token: robotAccessToken, robot_id: robotId }))
    }

    ws.onmessage = (event: MessageEvent) => {
      if (event.data instanceof Blob) {
        if (status.value !== 'connected') {
          status.value = 'connected'
          reconnectDelayMs = MIN_RECONNECT_DELAY_MS
        }
        void paintFrame(event.data)
        return
      }

      const data = JSON.parse(event.data)
      if (status.value === 'authenticating' && data.message !== 'success auth') {
        status.value = 'error'
        error.value = data.message || 'Error de autenticación de video'
        authFailed = true
      }
    }

    ws.onerror = () => {
      status.value = 'error'
      error.value = 'Error de conexión de video'
    }

    ws.onclose = () => {
      if (reconnectTimer !== null) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
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

  function disconnect() {
    manualDisconnect = true
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (ws) {
      ws.close()
      ws = null
    }
    status.value = 'disconnected'
  }

  return {
    status: readonly(status),
    error,
    connect,
    disconnect,
  }
}
