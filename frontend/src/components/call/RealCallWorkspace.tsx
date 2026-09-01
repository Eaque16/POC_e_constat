import { useCallback, useEffect, useRef, useState } from "react";
import { AudioLines, Bot, Check, CircleStop, FileCheck2, Gauge, LoaderCircle, Mic, PhoneCall, PhoneOff, RotateCcw, Save, Send, ShieldCheck, UserRound, Volume2 } from "lucide-react";
import { saveConversationClaim, sendConversationTurn, startConversation, transcribeAnswer, type ConversationState } from "@/services/conversation";
import { useAutomaticSpeechCapture, type SpeechMeasurement } from "@/hooks/useAutomaticSpeechCapture";

interface Message { role: "assistant" | "client"; text: string }
interface TurnPerformance {
  id: string; field: string; transcript: string; speechMs: number; endpointDelayMs: number;
  transcriptionMs: number; asrMs: number; understandingMs: number; persistenceMs: number;
  responseGapMs: number; agentSpeechMs?: number; totalMs: number;
}
interface TurnTiming { id: string; measurement: SpeechMeasurement; transcriptionMs: number; asrMs: number; field: string }
const SESSION_KEY = "econstat_active_conversation";
const VOICE_KEY = "econstat_preferred_voice";

function conversationSignal(text: string) {
  const value = text.toLowerCase();
  if (/bless|danger|saign|urgence|bloqu/.test(value)) return { label: "Urgence exprimée", action: "Vérifier immédiatement la sécurité", tone: "danger" };
  if (/paniqu|peur|stress|angoiss|trembl/.test(value)) return { label: "Stress déclaré", action: "Ralentir et poser une question courte", tone: "warning" };
  if (/je ne comprends|je ne sais pas|répétez|perdu/.test(value)) return { label: "Confusion possible", action: "Reformuler simplement", tone: "warning" };
  return { label: "Aucun signal explicite", action: "Continuer normalement", tone: "neutral" };
}

const LABELS: Record<string, string> = {
  nom_assure: "Assuré", telephone_assure: "Téléphone", assureur: "Assureur", plaque: "Immatriculation",
  date_accident: "Date", heure_accident: "Heure", lieu: "Lieu", type_accident: "Type d’accident",
  nombre_vehicules: "Véhicules", tiers_impliques: "Tiers impliqué", circonstances: "Circonstances",
  dommages: "Dommages", zone_endommagee: "Zone endommagée", vehicule_immobilise: "Véhicule immobilisé",
};

function speak(text: string, voiceName?: string, events?: { onStart?: (startedAt: number) => void; onEnd?: (durationMs: number) => void }) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.replace(/\n+/g, " "));
  const voices = window.speechSynthesis.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith("fr"));
  const preferred = voices.find((voice) => voice.name === voiceName) ?? voices.find((voice) => /natural|denise|vivienne|henri|google/i.test(voice.name)) ?? voices[0];
  if (preferred) utterance.voice = preferred;
  utterance.lang = preferred?.lang ?? "fr-FR"; utterance.rate = 0.94; utterance.pitch = 1.02;
  let startedAt = 0;
  utterance.onstart = () => { startedAt = performance.now(); events?.onStart?.(startedAt); };
  utterance.onend = () => events?.onEnd?.(startedAt ? performance.now() - startedAt : 0);
  utterance.onerror = () => events?.onEnd?.(startedAt ? performance.now() - startedAt : 0);
  window.speechSynthesis.speak(utterance);
}

export function RealCallWorkspace() {
  const [active, setActive] = useState(false);
  const [state, setState] = useState<ConversationState | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [progress, setProgress] = useState(0);
  const [complete, setComplete] = useState(false);
  const [recording, setRecording] = useState(false);
  const [processing, setProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [savedClaim, setSavedClaim] = useState<string | null>(null);
  const [claimId, setClaimId] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([]);
  const [voiceName, setVoiceName] = useState(() => localStorage.getItem(VOICE_KEY) ?? "");
  const [handsFree, setHandsFree] = useState(true);
  const [assistantSpeaking, setAssistantSpeaking] = useState(false);
  const [signal, setSignal] = useState(() => conversationSignal(""));
  const [latency, setLatency] = useState<{ audioMs: number; transcriptionMs: number; responseMs: number; totalMs: number } | null>(null);
  const [turnMetrics, setTurnMetrics] = useState<TurnPerformance[]>([]);
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const loadVoices = () => {
      const french = window.speechSynthesis?.getVoices().filter((voice) => voice.lang.toLowerCase().startsWith("fr")) ?? [];
      setVoices(french);
      if (!voiceName && french.length) {
        const preferred = french.find((voice) => /natural|denise|vivienne|henri|google/i.test(voice.name)) ?? french[0];
        setVoiceName(preferred.name);
      }
    };
    loadVoices(); window.speechSynthesis?.addEventListener("voiceschanged", loadVoices);
    try {
      const saved = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null") as { state: ConversationState; messages: Message[]; progress: number; complete: boolean; claimId: string | null; turnMetrics?: TurnPerformance[] } | null;
      if (saved?.state) { setState(saved.state); setMessages(saved.messages ?? []); setProgress(saved.progress ?? 0); setComplete(Boolean(saved.complete)); setClaimId(saved.claimId); setTurnMetrics(saved.turnMetrics ?? []); setActive(true); setSaveStatus("saved"); }
    } catch { localStorage.removeItem(SESSION_KEY); }
    return () => window.speechSynthesis?.removeEventListener("voiceschanged", loadVoices);
  // La restauration ne doit être exécutée qu'au montage.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => {
    if (!active || turnMetrics.length === 0) return;
    try {
      const snapshot = JSON.parse(localStorage.getItem(SESSION_KEY) ?? "null") as Record<string, unknown> | null;
      if (snapshot) localStorage.setItem(SESSION_KEY, JSON.stringify({ ...snapshot, turnMetrics }));
    } catch { /* La mesure reste visible en mémoire si le stockage navigateur est indisponible. */ }
  }, [active, turnMetrics]);
  useEffect(() => () => { streamRef.current?.getTracks().forEach((track) => track.stop()); window.speechSynthesis?.cancel(); }, []);

  const begin = async () => {
    setProcessing(true); setError(null); setSavedClaim(null);
    try {
      const result = await startConversation();
      setState(result.state); setProgress(result.progress); setComplete(result.complete);
      const initialMessages: Message[] = [{ role: "assistant", text: result.reply }];
      setMessages(initialMessages); setActive(true); setClaimId(null); setSaveStatus("idle");
      localStorage.setItem(SESSION_KEY, JSON.stringify({ state: result.state, messages: initialMessages, progress: result.progress, complete: result.complete, claimId: null }));
      speak(result.reply, voiceName, { onStart: () => setAssistantSpeaking(true), onEnd: () => setAssistantSpeaking(false) });
    } catch { setError("Le moteur conversationnel est indisponible. Vérifiez que l’API est démarrée."); }
    finally { setProcessing(false); }
  };

  const updateTurnMetric = (id: string, changes: Partial<TurnPerformance>) => setTurnMetrics((items) => items.map((item) => item.id === id ? { ...item, ...changes } : item));

  const submitTranscript = async (message: string, confidence = 1, timing?: TurnTiming) => {
    if (!state || !message.trim()) return;
    setProcessing(true); setError(null); setMessages((items) => [...items, { role: "client", text: message.trim() }]);
    try {
      const understandingStarted = performance.now();
      const result = await sendConversationTurn(message.trim(), state, confidence);
      const understandingRoundTrip = performance.now() - understandingStarted;
      const nextMessages = [...messages, { role: "client" as const, text: message.trim() }, { role: "assistant" as const, text: result.reply }];
      setState(result.state); setProgress(result.progress); setComplete(result.complete); setMessages(nextMessages);
      setSaveStatus("saving");
      try {
        const persistenceStarted = performance.now();
        const saved = await saveConversationClaim(result.state, claimId, false);
        const persistenceRoundTrip = performance.now() - persistenceStarted;
        setClaimId(saved.claim_id); setSaveStatus("saved");
        localStorage.setItem(SESSION_KEY, JSON.stringify({ state: result.state, messages: nextMessages, progress: result.progress, complete: result.complete, claimId: saved.claim_id }));
        if (timing) {
          const readyAt = performance.now();
          const metric: TurnPerformance = {
            id: timing.id, field: timing.field, transcript: message.trim(),
            speechMs: timing.measurement.speechMs,
            endpointDelayMs: timing.measurement.endpointDelayMs,
            transcriptionMs: timing.transcriptionMs,
            asrMs: timing.asrMs,
            understandingMs: result.metrics?.understanding_ms ?? understandingRoundTrip,
            persistenceMs: saved.metrics?.persistence_ms ?? persistenceRoundTrip,
            responseGapMs: readyAt - timing.measurement.endpointAt,
            totalMs: readyAt - timing.measurement.speechStartedAt,
          };
          setTurnMetrics((items) => [...items, metric]);
          window.setTimeout(() => speak(result.reply, voiceName, {
            onStart: (ttsStartedAt) => updateTurnMetric(timing.id, {
              responseGapMs: ttsStartedAt - timing.measurement.endpointAt,
              totalMs: ttsStartedAt - timing.measurement.speechStartedAt,
            }),
            onEnd: (agentSpeechMs) => { setAssistantSpeaking(false); updateTurnMetric(timing.id, { agentSpeechMs }); },
          }), 0);
          setAssistantSpeaking(true);
          setLatency({ audioMs: Math.round(metric.speechMs), transcriptionMs: Math.round(metric.transcriptionMs), responseMs: Math.round(metric.understandingMs + metric.persistenceMs), totalMs: Math.round(metric.responseGapMs) });
        } else speak(result.reply, voiceName, { onStart: () => setAssistantSpeaking(true), onEnd: () => setAssistantSpeaking(false) });
      } catch {
        setSaveStatus("error");
        localStorage.setItem(SESSION_KEY, JSON.stringify({ state: result.state, messages: nextMessages, progress: result.progress, complete: result.complete, claimId }));
        setError("La réponse est conservée sur cet appareil, mais la sauvegarde serveur a échoué.");
        speak(result.reply, voiceName, { onStart: () => setAssistantSpeaking(true), onEnd: () => setAssistantSpeaking(false) });
      }
      setSignal(conversationSignal(message));
    } catch { setError("La réponse n’a pas pu être traitée par le moteur conversationnel."); }
    finally { setProcessing(false); }
  };

  const processAutomaticAudio = useCallback(async (audio: Blob, measurement: SpeechMeasurement) => {
    const startedAt = performance.now(); setProcessing(true); setError(null);
    try {
      const result = await transcribeAnswer(audio);
      const transcriptionMs = performance.now() - startedAt;
      if (!result.text.trim()) { setError("Aucune parole distincte n’a été détectée. Je continue d’écouter."); setProcessing(false); return; }
      await submitTranscript(result.text, result.confidence, {
        id: crypto.randomUUID(), measurement, transcriptionMs,
        asrMs: result.metrics?.asr_ms ?? transcriptionMs,
        field: state?.current_field ?? "information complémentaire",
      });
    } catch { setError("Whisper n’a pas pu transcrire cette prise. Le microphone reste à l’écoute."); setProcessing(false); }
  // submitTranscript utilise volontairement le dernier état rendu ; le hook actualise le callback à chaque rendu.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state, claimId, messages, voiceName]);

  const automaticCapture = useAutomaticSpeechCapture({
    enabled: active && handsFree && !complete,
    suspended: processing || assistantSpeaking,
    silenceMs: 850,
    maxUtteranceMs: 20_000,
    onSpeechStart: () => window.speechSynthesis?.cancel(),
    onUtterance: processAutomaticAudio,
  });

  const startRecording = async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream; chunksRef.current = [];
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? "audio/webm;codecs=opus" : "audio/webm";
      const recorder = new MediaRecorder(stream, { mimeType }); recorderRef.current = recorder;
      recorder.ondataavailable = (event) => { if (event.data.size) chunksRef.current.push(event.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop()); streamRef.current = null;
        const audio = new Blob(chunksRef.current, { type: mimeType });
        if (!audio.size) { setError("Aucun son n’a été enregistré."); return; }
        setProcessing(true);
        try { const result = await transcribeAnswer(audio); await submitTranscript(result.text, result.confidence); }
        catch { setError("Whisper n’a pas pu transcrire cette réponse. Réessayez ou utilisez la saisie texte."); setProcessing(false); }
      };
      recorder.start(); setRecording(true);
    } catch { setError("Accès au microphone refusé ou périphérique indisponible."); }
  };

  const stopRecording = () => { if (recorderRef.current?.state === "recording") recorderRef.current.stop(); setRecording(false); };
  const sendText = () => { const value = text; setText(""); void submitTranscript(value); };
  const save = async () => {
    if (!state) return; setProcessing(true); setError(null);
    try { const result = await saveConversationClaim(state, claimId, true); setSavedClaim(result.claim_id); setClaimId(result.claim_id); setSaveStatus("saved"); localStorage.removeItem(SESSION_KEY); }
    catch (reason) { setError(`Le dossier n’a pas pu être finalisé${reason instanceof Error ? ` : ${reason.message}` : "."}`); }
    finally { setProcessing(false); }
  };
  const reset = () => { setActive(false); setState(null); setMessages([]); setProgress(0); setComplete(false); setSavedClaim(null); setClaimId(null); setSaveStatus("idle"); setAssistantSpeaking(false); setSignal(conversationSignal("")); setLatency(null); setTurnMetrics([]); setError(null); localStorage.removeItem(SESSION_KEY); window.speechSynthesis?.cancel(); };

  if (!active) return (
    <div className="mx-auto flex min-h-[70vh] max-w-3xl items-center justify-center">
      <section className="w-full overflow-hidden rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-xl shadow-slate-900/5 lg:p-12">
        <div className="mx-auto grid h-20 w-20 place-items-center rounded-3xl bg-gradient-to-br from-blue-600 to-blue-950 text-white shadow-xl shadow-blue-900/20"><PhoneCall className="h-9 w-9" /></div>
        <p className="mt-6 text-xs font-bold uppercase tracking-[.18em] text-primary">Poste d’appel connecté</p><h1 className="mt-2 text-3xl font-bold tracking-tight">Démarrer une pré-déclaration réelle</h1><p className="mx-auto mt-3 max-w-xl text-sm leading-6 text-muted-foreground">Chaque réponse micro sera transcrite par Whisper puis analysée par le moteur conversationnel. Aucune conversation fictive ne sera injectée.</p>
        <div className="mx-auto mt-7 grid max-w-lg gap-3 text-left sm:grid-cols-3">{[[Mic,"Whisper local"],[Bot,"Assistant métier"],[ShieldCheck,"Contrôle humain"]].map(([Icon,label]) => { const I = Icon as typeof Mic; return <div key={String(label)} className="flex items-center gap-2 rounded-xl bg-slate-50 p-3 text-xs font-semibold"><I className="h-4 w-4 text-primary" />{label as string}</div>; })}</div>
        {error && <p className="mt-5 rounded-xl bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button onClick={begin} disabled={processing} className="mt-7 inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-6 text-sm font-bold text-white shadow-lg transition hover:-translate-y-0.5 disabled:opacity-60">{processing ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <PhoneCall className="h-4 w-4" />} Démarrer l’appel</button>
      </section>
    </div>
  );

  const data = state?.data ?? {};
  const mean = (key: keyof TurnPerformance) => turnMetrics.length ? turnMetrics.reduce((sum, item) => sum + (typeof item[key] === "number" ? item[key] : 0), 0) / turnMetrics.length : 0;
  return <div className="space-y-5">
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-emerald-600">● Appel connecté au modèle</p><h1 className="mt-1 text-2xl font-bold">Pré-déclaration en cours</h1><p className={`mt-1 flex items-center gap-1.5 text-xs ${saveStatus === "error" ? "text-red-600" : "text-muted-foreground"}`}><Save className="h-3.5 w-3.5" />{saveStatus === "saving" ? "Sauvegarde en cours…" : saveStatus === "saved" ? "Brouillon sauvegardé automatiquement" : saveStatus === "error" ? "Sauvegarde locale uniquement" : "La sauvegarde démarre après la première réponse"}</p></div><div className="flex flex-wrap items-center gap-2"><button onClick={() => setHandsFree((value) => !value)} className={`inline-flex h-10 items-center gap-2 rounded-xl px-3 text-xs font-bold ${handsFree ? "bg-emerald-100 text-emerald-800" : "border bg-white text-slate-600"}`}><AudioLines className="h-4 w-4" />{handsFree ? "Mains libres actif" : "Mode manuel"}</button><label className="flex h-10 items-center gap-2 rounded-xl border bg-white px-3 text-xs font-semibold"><Volume2 className="h-4 w-4 text-primary" /><select value={voiceName} onChange={(event) => { setVoiceName(event.target.value); localStorage.setItem(VOICE_KEY, event.target.value); }} className="max-w-40 bg-transparent outline-none">{voices.length ? voices.map((voice) => <option key={voice.name} value={voice.name}>{voice.name}</option>) : <option>Voix française système</option>}</select></label><button onClick={reset} className="inline-flex h-10 items-center gap-2 rounded-xl border bg-white px-4 text-sm font-semibold"><RotateCcw className="h-4 w-4" /> Recommencer</button><button onClick={reset} className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white"><PhoneOff className="h-4 w-4" /> Terminer</button></div></div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} /></div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,.75fr)]">
      <section className="flex min-h-[38rem] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><header className="flex items-center justify-between border-b bg-slate-50/70 px-5 py-4"><div className="flex items-center gap-2 text-sm font-bold"><Bot className="h-4 w-4 text-primary" /> Conversation réelle</div><span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">Progression {progress}%</span></header><div className="flex-1 space-y-4 overflow-y-auto p-5">{messages.map((message,index) => <div key={index} className={`flex gap-3 ${message.role === "client" ? "flex-row-reverse" : ""}`}><div className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${message.role === "assistant" ? "bg-primary text-white" : "bg-emerald-100 text-emerald-700"}`}>{message.role === "assistant" ? <Bot className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}</div><div className={`max-w-[78%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "assistant" ? "rounded-tl-sm bg-slate-100" : "rounded-tr-sm bg-primary text-white"}`}>{message.text}</div></div>)}{processing && <div className="flex items-center gap-2 text-xs text-muted-foreground"><LoaderCircle className="h-4 w-4 animate-spin" /> Le modèle traite la réponse…</div>}<div ref={transcriptEndRef} /></div>
        <footer className="border-t bg-slate-50 p-4">{(error || automaticCapture.error) && <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-xs text-red-700">{error ?? automaticCapture.error}</p>}{handsFree && !complete && <div className="mb-3 flex items-center gap-3 rounded-xl border border-emerald-100 bg-emerald-50 px-3 py-2"><div className="flex h-7 items-end gap-0.5">{[.35,.55,.8,1,.7].map((ratio,index) => <span key={index} className="w-1 rounded-full bg-emerald-500 transition-all" style={{ height: `${Math.max(3, automaticCapture.level * 24 * ratio)}px` }} />)}</div><div><p className="text-xs font-bold text-emerald-800">{automaticCapture.status === "speech" ? "Je vous écoute…" : automaticCapture.status === "endpointing" || processing ? "Traitement de votre réponse…" : automaticCapture.status === "starting" ? "Activation du microphone…" : "Parlez naturellement, aucun bouton nécessaire"}</p><p className="text-[10px] text-emerald-700/70">La réponse part automatiquement après 0,85 s de silence.</p></div></div>}<div className="flex gap-2">{!handsFree && <button onClick={recording ? stopRecording : startRecording} disabled={processing || complete} className={`inline-flex h-11 min-w-44 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold text-white transition disabled:opacity-50 ${recording ? "animate-pulse bg-red-600" : "bg-primary"}`}>{recording ? <><CircleStop className="h-4 w-4" /> Arrêter et transcrire</> : <><Mic className="h-4 w-4" /> Répondre au micro</>}</button>}<div className="flex flex-1"><input value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") sendText(); }} disabled={processing || complete} placeholder="Ou corriger/répondre par écrit…" className="h-11 min-w-0 flex-1 rounded-l-xl border border-r-0 bg-white px-3 text-sm outline-none focus:border-primary" /><button onClick={sendText} disabled={!text.trim() || processing || complete} className="grid h-11 w-11 place-items-center rounded-r-xl bg-slate-900 text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></div></div></footer>
      </section>
      <aside className="space-y-4"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="flex items-center gap-2 font-bold"><FileCheck2 className="h-5 w-5 text-primary" /> Informations recueillies</h2><div className="mt-4 space-y-1">{Object.entries(data).filter(([key,value]) => value !== null && value !== undefined && !["firstname","lastname"].includes(key)).map(([key,value]) => <div key={key} className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 text-xs"><span className="text-muted-foreground">{LABELS[key] ?? key.replaceAll("_", " ")}</span><strong className="max-w-[55%] text-right">{typeof value === "boolean" ? (value ? "Oui" : "Non") : String(value)}</strong></div>)}{Object.keys(data).length === 0 && <p className="py-5 text-center text-xs text-muted-foreground">Les informations apparaîtront ici.</p>}</div></section><section className={`rounded-2xl border p-4 ${signal.tone === "danger" ? "border-red-200 bg-red-50" : signal.tone === "warning" ? "border-amber-200 bg-amber-50" : "border-slate-200 bg-white"}`}><p className="text-xs font-bold">Signal conversationnel : {signal.label}</p><p className="mt-1 text-[11px] text-muted-foreground">{signal.action}. Indication non clinique fondée uniquement sur les mots prononcés.</p></section>{latency && <section className="rounded-2xl border border-slate-200 bg-white p-4"><h3 className="flex items-center gap-2 text-xs font-bold"><Gauge className="h-4 w-4 text-primary" /> Latence du dernier échange</h3><div className="mt-3 grid grid-cols-2 gap-2 text-[11px]"><span>Parole <strong className="float-right">{(latency.audioMs/1000).toFixed(1)} s</strong></span><span>Whisper <strong className="float-right">{(latency.transcriptionMs/1000).toFixed(1)} s</strong></span><span>Compréhension <strong className="float-right">{(latency.responseMs/1000).toFixed(1)} s</strong></span><span>Total après silence <strong className="float-right">{(latency.totalMs/1000).toFixed(1)} s</strong></span></div></section>}{complete && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><div className="flex items-center gap-2 font-bold text-emerald-800"><Check className="h-5 w-5" /> Recueil terminé</div><p className="mt-2 text-xs leading-5 text-emerald-700">Vos informations ont bien été notées. Merci.</p>{savedClaim ? <p className="mt-4 rounded-xl bg-white p-3 text-xs font-semibold text-emerald-800">Dossier enregistré : {savedClaim}</p> : <button onClick={save} disabled={processing} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-emerald-700 text-sm font-bold text-white"><FileCheck2 className="h-4 w-4" /> Enregistrer la fiche</button>}</section>}</aside>
    </div>
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-col justify-between gap-3 border-b border-slate-100 p-5 sm:flex-row sm:items-center"><div><h2 className="flex items-center gap-2 font-bold"><Gauge className="h-5 w-5 text-primary" /> Observateur de latence</h2><p className="mt-1 text-xs text-muted-foreground">Mesures parallèles, sans modifier les décisions du moteur conversationnel.</p></div>{turnMetrics.length > 0 && <div className="flex gap-3 text-xs"><span>Moyenne transcription <strong>{(mean("transcriptionMs")/1000).toFixed(2)} s</strong></span><span>Décalage moyen <strong>{(mean("responseGapMs")/1000).toFixed(2)} s</strong></span></div>}</div>
      {turnMetrics.length === 0 ? <p className="p-6 text-center text-xs text-muted-foreground">Les mesures apparaîtront après la première réponse vocale.</p> : <div className="overflow-x-auto"><table className="w-full text-xs"><thead className="bg-slate-50 text-left text-[10px] uppercase tracking-wider text-slate-500"><tr><th className="px-4 py-3">Information</th><th className="px-4 py-3">Parole</th><th className="px-4 py-3">Fin détectée</th><th className="px-4 py-3">Transcription</th><th className="px-4 py-3">Whisper pur</th><th className="px-4 py-3">Compréhension</th><th className="px-4 py-3">Sauvegarde</th><th className="px-4 py-3">Décalage réponse</th><th className="px-4 py-3">Réponse agent</th></tr></thead><tbody className="divide-y divide-slate-100">{turnMetrics.slice().reverse().map((item) => <tr key={item.id} title={item.transcript} className="hover:bg-slate-50"><td className="max-w-40 truncate px-4 py-3 font-semibold">{LABELS[item.field] ?? item.field.replaceAll("_", " ")}</td><td className="px-4 py-3">{(item.speechMs/1000).toFixed(2)} s</td><td className="px-4 py-3">{(item.endpointDelayMs/1000).toFixed(2)} s</td><td className="px-4 py-3">{(item.transcriptionMs/1000).toFixed(2)} s</td><td className="px-4 py-3">{(item.asrMs/1000).toFixed(2)} s</td><td className="px-4 py-3">{item.understandingMs.toFixed(0)} ms</td><td className="px-4 py-3">{item.persistenceMs.toFixed(0)} ms</td><td className="px-4 py-3 font-bold text-primary">{(item.responseGapMs/1000).toFixed(2)} s</td><td className="px-4 py-3">{item.agentSpeechMs === undefined ? "en cours…" : `${(item.agentSpeechMs/1000).toFixed(2)} s`}</td></tr>)}</tbody></table></div>}
    </section>
  </div>;
}
