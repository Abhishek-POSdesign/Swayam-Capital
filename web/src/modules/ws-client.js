/**
 * WebSocket client for live NIFTY spot tick streaming.
 */

export class SpotWebSocketClient {
  constructor(onTick) {
    this.onTick = onTick;
    this.ws = null;
    this.reconnectTimeout = null;
  }

  connect() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const url = `${protocol}//${host}/ws/spot`;

    try {
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        console.log('Connected to spot WebSocket stream.');
      };

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.spot && this.onTick) {
            this.onTick(data.spot);
          }
        } catch (e) {
          // Keep-alive or non-JSON frame
        }
      };

      this.ws.onclose = () => {
        console.warn('Spot WebSocket closed. Reconnecting in 3s...');
        this.reconnectTimeout = setTimeout(() => this.connect(), 3000);
      };

      this.ws.onerror = (err) => {
        console.warn('Spot WebSocket encountered error:', err);
      };
    } catch (err) {
      console.warn('Could not establish WebSocket, falling back to REST poll:', err);
    }
  }

  disconnect() {
    if (this.reconnectTimeout) clearTimeout(this.reconnectTimeout);
    if (this.ws) this.ws.close();
  }
}
