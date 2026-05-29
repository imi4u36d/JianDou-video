export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private onMessage: (data: any) => void
  private reconnectDelay = 2000
  private maxReconnectDelay = 30000
  private shouldReconnect = true

  constructor(url: string, onMessage: (data: any) => void) {
    this.url = url
    this.onMessage = onMessage
  }

  connect() {
    this.shouldReconnect = true
    this._connect()
  }

  private _connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const fullUrl = `${protocol}//${window.location.host}${this.url}`

    try {
      this.ws = new WebSocket(fullUrl)
      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.type === 'pong') return
          this.onMessage(data)
        } catch {
          // Ignore non-JSON messages
        }
      }
      this.ws.onopen = () => {
        this.reconnectDelay = 2000 // Reset on successful connection
        // Send periodic pings
        const pingInterval = setInterval(() => {
          if (this.ws?.readyState === WebSocket.OPEN) {
            this.ws.send('ping')
          } else {
            clearInterval(pingInterval)
          }
        }, 25000)
      }
      this.ws.onerror = () => {
        // Will trigger onclose
      }
      this.ws.onclose = () => {
        if (this.shouldReconnect) {
          setTimeout(() => this._connect(), this.reconnectDelay)
          this.reconnectDelay = Math.min(this.reconnectDelay * 1.5, this.maxReconnectDelay)
        }
      }
    } catch {
      if (this.shouldReconnect) {
        setTimeout(() => this._connect(), this.reconnectDelay)
      }
    }
  }

  send(data: any) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }

  disconnect() {
    this.shouldReconnect = false
    this.ws?.close()
    this.ws = null
  }
}
