import { API_URL, ApiError, getToken } from "@/services/api";

export interface ConversationState {
  data: Record<string, unknown>;
  field_records: Record<string, Record<string, unknown>>;
  transcript: string[];
  current_field: string | null;
  [key: string]: unknown;
}

export interface ConversationResult {
  reply: string;
  state: ConversationState;
  progress: number;
  complete: boolean;
  metrics?: { understanding_ms?: number };
}

export interface TranscriptionResult {
  text: string;
  confidence: number;
  metrics?: { cold_start_ms?: number; audio_decode_ms?: number; vad_ms?: number; asr_ms?: number; total_turn_ms?: number };
}

async function parseResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let message = `Erreur ${response.status}`;
    try { const body = await response.json() as { detail?: unknown }; message = body.detail ? String(body.detail) : message; } catch { /* réponse non JSON */ }
    throw new ApiError(response.status, message);
  }
  return response.json() as Promise<T>;
}

function headers(contentType = "application/json"): Headers {
  const result = new Headers({ "Content-Type": contentType });
  const token = getToken();
  if (token) result.set("Authorization", `Bearer ${token}`);
  return result;
}

export async function startConversation(): Promise<ConversationResult> {
  return parseResponse(await fetch(`${API_URL}/conversations/start`, { method: "POST", headers: headers() }));
}

export async function transcribeAnswer(audio: Blob): Promise<TranscriptionResult> {
  const response = await fetch(`${API_URL}/transcription/chunk`, {
    method: "POST",
    headers: headers(audio.type || "audio/webm"),
    body: audio,
  });
  return parseResponse(response);
}

export async function sendConversationTurn(message: string, state: ConversationState, asrConfidence = 0.75): Promise<ConversationResult> {
  return parseResponse(await fetch(`${API_URL}/conversations/respond`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ message, state, asr_confidence: asrConfidence }),
  }));
}

const CLAIM_FIELDS = new Set(["nom_assure", "telephone_assure", "assureur", "lieu", "date_accident", "heure_accident", "type_accident", "nombre_vehicules", "dommages", "zone_endommagee", "vehicule_immobilise", "plaque", "besoin_assistance", "tiers_impliques", "tiers", "circonstances", "blesses", "informations_complementaires"]);

export async function saveConversationClaim(state: ConversationState, claimId?: string | null, complete = false): Promise<{ claim_id: string; call_id: string; missing_fields: string[]; status: string; metrics?: { persistence_ms?: number } }> {
  const data = Object.fromEntries(Object.entries(state.data).filter(([key]) => CLAIM_FIELDS.has(key)));
  const response = await fetch(`${API_URL}/conversations/claims`, {
    method: "POST",
    headers: headers(),
    body: JSON.stringify({ data, transcript: state.transcript, field_records: state.field_records, claim_id: claimId || null, complete }),
  });
  return parseResponse(response);
}
