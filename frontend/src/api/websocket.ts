import type { WSEvent } from '../types/api'

type Callback = (event: WSEvent) => void

class WebSocketManager {
  private ws: WebSocket | null = null
  private listeners = new Set<Callback>()
  private projectId: number | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private pingTimer: ReturnType<typeof setInterval> | null = null
  private backoff = 1000
  private maxBackoff = 30000
  private intentionalClose = false

  connect(projectId: number) {
    if (this.projectId === projectId && this.ws?.readyState === WebSocket.OPEN) {
      return
    }

    this.disconnect()
    this.projectId = projectId
    this.intentionalClose = false
    this.openConnection()
  }

  disconnect() {
    this.intentionalClose = true
    this.clearTimers()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.projectId = null
    this.backoff = 1000
  }

  subscribe(cb: Callback) {
    this.listeners.add(cb)
  }

  unsubscribe(cb: Callback) {
    this.listeners.delete(cb)
  }

  private openConnection() {
    if (this.projectId == null) return

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${location.host}/ws?project_id=${this.projectId}`

    this.ws = new WebSocket(url)

    this.ws.onopen = () => {
      this.backoff = 1000
      this.startPing()
    }

    this.ws.onmessage = (e) => {
      if (e.data === 'pong') return
      try {
        const event: WSEvent = JSON.parse(e.data)
        this.listeners.forEach((cb) => cb(event))
      } catch {}
    }

    this.ws.onclose = () => {
      this.clearTimers()
      if (!this.intentionalClose) {
        this.scheduleReconnect()
      }
    }

    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  private startPing() {
    this.pingTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping')
      }
    }, 30000)
  }

  private scheduleReconnect() {
    this.reconnectTimer = setTimeout(() => {
      this.openConnection()
      this.backoff = Math.min(this.backoff * 2, this.maxBackoff)
    }, this.backoff)
  }

  private clearTimers() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
      this.reconnectTimer = null
    }
    if (this.pingTimer) {
      clearInterval(this.pingTimer)
      this.pingTimer = null
    }
  }
}

export const wsManager = new WebSocketManager()
