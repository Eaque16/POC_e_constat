import type {
  ConnectionMode,
  ConnectionStatus,
  TranscriptSpeaker,
  TranscriptTurn,
} from "@/types/transcription";

const WS_URL = import.meta.env.VITE_TRANSCRIPTION_WS_URL;
const REST_URL = import.meta.env.VITE_TRANSCRIPTION_REST_URL;
const WS_CONNECT_TIMEOUT_MS = 3000;
const REST_REQUEST_TIMEOUT_MS = 15000;

const DEMO_SCRIPT: { speaker: TranscriptSpeaker; text: string }[] = [
  { speaker: "assure", text: "Bonjour, j'ai eu un accident ce matin a Cocody." },
  { speaker: "agent", text: "Bonjour, je vais vous aider a declarer votre sinistre." },
  { speaker: "assure", text: "C'est un accrochage avec une autre voiture au feu rouge." },
  { speaker: "agent", text: "Y a-t-il des blesses ou des degats importants ?" },
  { speaker: "assure", text: "Non, pas de blesses, juste le pare-choc abime." },
];

interface TranscriptionCallbacks {
  onStatusChange: (status: ConnectionStatus, mode: ConnectionMode) => void;
  onTurn: (turn: TranscriptTurn) => void;
  onError: (message: string) => void;
}

let turnCounter = 0;
function nextTurnId(): string {
  turnCounter += 1;
  return `turn-${turnCounter}`;
}

export class TranscriptionSession {
  private callbacks: TranscriptionCallbacks;
  private mode: ConnectionMode = "demo";
  private ws: WebSocket | null = null;
  private demoIndex = 0;
  private demoTimer: ReturnType<typeof setInterval> | null = null;
  private demoTurnTimers = new Set<ReturnType<typeof setTimeout>>();
  private controllers = new Set<AbortController>();
  private closed = false;

  constructor(callbacks: TranscriptionCallbacks) {
    this.callbacks = callbacks;
  }

  async start(): Promise<void> {
    if (this.closed) return;
    this.callbacks.onStatusChange("connecting", this.mode);

    const wsOk = await this.tryWebSocket();
    if (this.closed) return;
    if (wsOk) {
      this.mode = "websocket";
      this.callbacks.onStatusChange("listening", this.mode);
      return;
    }

    const restOk = await this.tryRestPing();
    if (this.closed) return;
    if (restOk) {
      this.mode = "rest";
      this.callbacks.onStatusChange("listening", this.mode);
      return;
    }

    this.mode = "demo";
    this.callbacks.onStatusChange("listening", this.mode);
    this.startDemoLoop();
  }

  private tryWebSocket(): Promise<boolean> {
    if (!WS_URL || this.closed) return Promise.resolve(false);
    return new Promise((resolve) => {
      let settled = false;
      let timeout: ReturnType<typeof setTimeout> | undefined;
      const finish = (result: boolean) => {
        if (settled) return;
        settled = true;
        if (timeout) clearTimeout(timeout);
        resolve(result);
      };
      try {
        const socket = new WebSocket(WS_URL);
        timeout = setTimeout(() => {
          socket.close();
          finish(false);
        }, WS_CONNECT_TIMEOUT_MS);

        socket.onopen = () => {
          if (this.closed) {
            socket.close();
            finish(false);
            return;
          }
          this.ws = socket;
          finish(true);
        };

        socket.onerror = () => {
          socket.close();
          finish(false);
        };

        socket.onmessage = (event) => {
          this.handleIncomingMessage(event.data);
        };

        socket.onclose = () => {
          if (!this.closed && this.mode === "websocket") {
            this.callbacks.onStatusChange("reconnecting", this.mode);
          }
        };
      } catch {
        finish(false);
      }
    });
  }

  private async tryRestPing(): Promise<boolean> {
    if (!REST_URL || this.closed) return false;
    try {
      const controller = new AbortController();
      this.controllers.add(controller);
      const timeout = setTimeout(() => controller.abort(), WS_CONNECT_TIMEOUT_MS);
      const response = await fetch(REST_URL, {
        method: "OPTIONS",
        signal: controller.signal,
      });
      clearTimeout(timeout);
      this.controllers.delete(controller);
      return response.ok;
    } catch {
      return false;
    }
  }

  private handleIncomingMessage(raw: string) {
    try {
      const parsed = JSON.parse(raw) as {
        speaker?: TranscriptSpeaker;
        text?: string;
      };
      if (parsed.text) {
        this.callbacks.onTurn({
          id: nextTurnId(),
          speaker: parsed.speaker ?? "assure",
          text: parsed.text,
          timestamp: Date.now(),
        });
      }
    } catch {
      this.callbacks.onError("Reponse de transcription illisible.");
    }
  }

  private startDemoLoop() {
    this.demoTimer = setInterval(() => {
      if (this.demoIndex >= DEMO_SCRIPT.length) {
        return;
      }
      const line = DEMO_SCRIPT[this.demoIndex];
      this.demoIndex += 1;
      this.callbacks.onStatusChange("processing", this.mode);
      const timer = window.setTimeout(() => {
        this.demoTurnTimers.delete(timer);
        if (this.closed) return;
        this.callbacks.onTurn({
          id: nextTurnId(),
          speaker: line.speaker,
          text: line.text,
          timestamp: Date.now(),
        });
        this.callbacks.onStatusChange("listening", this.mode);
      }, 500);
      this.demoTurnTimers.add(timer);
    }, 4000);
  }

  async sendAudioChunk(blob: Blob): Promise<void> {
    if (this.closed) return;
    if (this.mode === "websocket" && this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.callbacks.onStatusChange("processing", this.mode);
      this.ws.send(await blob.arrayBuffer());
      return;
    }

    if (this.mode === "rest") {
      this.callbacks.onStatusChange("processing", this.mode);
      try {
        const controller = new AbortController();
        this.controllers.add(controller);
        const timeout = setTimeout(() => controller.abort(), REST_REQUEST_TIMEOUT_MS);
        const response = await fetch(REST_URL, {
          method: "POST",
          headers: { "Content-Type": "audio/webm" },
          body: blob,
          signal: controller.signal,
        });
        clearTimeout(timeout);
        this.controllers.delete(controller);
        if (response.ok) {
          const data = (await response.json()) as {
            speaker?: TranscriptSpeaker;
            text?: string;
          };
          if (data.text) {
            this.callbacks.onTurn({
              id: nextTurnId(),
              speaker: data.speaker ?? "assure",
              text: data.text,
              timestamp: Date.now(),
            });
          }
          this.callbacks.onStatusChange("listening", this.mode);
        } else {
          this.callbacks.onError("Le service de transcription a refuse le segment audio.");
          this.callbacks.onStatusChange("reconnecting", this.mode);
        }
      } catch {
        if (this.closed) return;
        this.callbacks.onError("Le service de transcription est indisponible.");
        this.callbacks.onStatusChange("reconnecting", this.mode);
      }
    }
    // en mode demo, les chunks audio sont ignores : le script demo tourne seul
  }

  getMode(): ConnectionMode {
    return this.mode;
  }

  close(): void {
    this.closed = true;
    if (this.demoTimer) clearInterval(this.demoTimer);
    this.demoTimer = null;
    this.demoTurnTimers.forEach((timer) => clearTimeout(timer));
    this.demoTurnTimers.clear();
    this.controllers.forEach((controller) => controller.abort());
    this.controllers.clear();
    if (this.ws) this.ws.close();
    this.callbacks.onStatusChange("offline", this.mode);
  }
}
