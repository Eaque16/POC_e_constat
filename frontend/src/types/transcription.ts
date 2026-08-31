export type TranscriptSpeaker = "agent" | "assure";

export interface TranscriptTurn {
  id: string;
  speaker: TranscriptSpeaker;
  text: string;
  timestamp: number;
}

export type ConnectionMode = "websocket" | "rest" | "demo";

export type ConnectionStatus =
  | "connecting"
  | "listening"
  | "processing"
  | "reconnecting"
  | "offline";
