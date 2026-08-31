import { useEffect, useRef, useState } from "react";
import { Bot, Check, CircleStop, FileCheck2, LoaderCircle, Mic, PhoneCall, PhoneOff, RotateCcw, Send, ShieldCheck, UserRound } from "lucide-react";
import { saveConversationClaim, sendConversationTurn, startConversation, transcribeAnswer, type ConversationState } from "@/services/conversation";

interface Message { role: "assistant" | "client"; text: string }

const LABELS: Record<string, string> = {
  nom_assure: "Assuré", telephone_assure: "Téléphone", assureur: "Assureur", plaque: "Immatriculation",
  date_accident: "Date", heure_accident: "Heure", lieu: "Lieu", type_accident: "Type d’accident",
  nombre_vehicules: "Véhicules", tiers_impliques: "Tiers impliqué", circonstances: "Circonstances",
  dommages: "Dommages", zone_endommagee: "Zone endommagée", vehicule_immobilise: "Véhicule immobilisé",
};

function speak(text: string) {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text.replace(/\n+/g, " "));
  utterance.lang = "fr-FR"; utterance.rate = 0.96;
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
  const recorderRef = useRef<MediaRecorder | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const transcriptEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => { transcriptEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);
  useEffect(() => () => { streamRef.current?.getTracks().forEach((track) => track.stop()); window.speechSynthesis?.cancel(); }, []);

  const begin = async () => {
    setProcessing(true); setError(null); setSavedClaim(null);
    try {
      const result = await startConversation();
      setState(result.state); setProgress(result.progress); setComplete(result.complete);
      setMessages([{ role: "assistant", text: result.reply }]); setActive(true); speak(result.reply);
    } catch { setError("Le moteur conversationnel est indisponible. Vérifiez que l’API est démarrée."); }
    finally { setProcessing(false); }
  };

  const submitTranscript = async (message: string, confidence = 1) => {
    if (!state || !message.trim()) return;
    setProcessing(true); setError(null); setMessages((items) => [...items, { role: "client", text: message.trim() }]);
    try {
      const result = await sendConversationTurn(message.trim(), state, confidence);
      setState(result.state); setProgress(result.progress); setComplete(result.complete);
      setMessages((items) => [...items, { role: "assistant", text: result.reply }]); speak(result.reply);
    } catch { setError("La réponse n’a pas pu être traitée par le moteur conversationnel."); }
    finally { setProcessing(false); }
  };

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
    try { const result = await saveConversationClaim(state); setSavedClaim(result.claim_id); }
    catch { setError("Le dossier n’a pas pu être créé. Vérifiez les informations recueillies."); }
    finally { setProcessing(false); }
  };
  const reset = () => { setActive(false); setState(null); setMessages([]); setProgress(0); setComplete(false); setSavedClaim(null); setError(null); window.speechSynthesis?.cancel(); };

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
  return <div className="space-y-5">
    <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center"><div><p className="text-xs font-bold uppercase tracking-[.16em] text-emerald-600">● Appel connecté au modèle</p><h1 className="mt-1 text-2xl font-bold">Pré-déclaration en cours</h1></div><div className="flex items-center gap-2"><button onClick={reset} className="inline-flex h-10 items-center gap-2 rounded-xl border bg-white px-4 text-sm font-semibold"><RotateCcw className="h-4 w-4" /> Recommencer</button><button onClick={reset} className="inline-flex h-10 items-center gap-2 rounded-xl bg-red-600 px-4 text-sm font-semibold text-white"><PhoneOff className="h-4 w-4" /> Terminer</button></div></div>
    <div className="h-2 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-gradient-to-r from-blue-600 to-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} /></div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1.5fr)_minmax(20rem,.75fr)]">
      <section className="flex min-h-[38rem] flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm"><header className="flex items-center justify-between border-b bg-slate-50/70 px-5 py-4"><div className="flex items-center gap-2 text-sm font-bold"><Bot className="h-4 w-4 text-primary" /> Conversation réelle</div><span className="rounded-full bg-blue-50 px-2.5 py-1 text-[11px] font-semibold text-blue-700">Progression {progress}%</span></header><div className="flex-1 space-y-4 overflow-y-auto p-5">{messages.map((message,index) => <div key={index} className={`flex gap-3 ${message.role === "client" ? "flex-row-reverse" : ""}`}><div className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${message.role === "assistant" ? "bg-primary text-white" : "bg-emerald-100 text-emerald-700"}`}>{message.role === "assistant" ? <Bot className="h-4 w-4" /> : <UserRound className="h-4 w-4" />}</div><div className={`max-w-[78%] whitespace-pre-line rounded-2xl px-4 py-3 text-sm leading-6 ${message.role === "assistant" ? "rounded-tl-sm bg-slate-100" : "rounded-tr-sm bg-primary text-white"}`}>{message.text}</div></div>)}{processing && <div className="flex items-center gap-2 text-xs text-muted-foreground"><LoaderCircle className="h-4 w-4 animate-spin" /> Le modèle traite la réponse…</div>}<div ref={transcriptEndRef} /></div>
        <footer className="border-t bg-slate-50 p-4">{error && <p className="mb-3 rounded-lg bg-red-50 p-2.5 text-xs text-red-700">{error}</p>}<div className="flex gap-2"><button onClick={recording ? stopRecording : startRecording} disabled={processing || complete} className={`inline-flex h-11 min-w-44 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold text-white transition disabled:opacity-50 ${recording ? "animate-pulse bg-red-600" : "bg-primary"}`}>{recording ? <><CircleStop className="h-4 w-4" /> Arrêter et transcrire</> : <><Mic className="h-4 w-4" /> Répondre au micro</>}</button><div className="flex flex-1"><input value={text} onChange={(event) => setText(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") sendText(); }} disabled={processing || complete} placeholder="Ou corriger/répondre par écrit…" className="h-11 min-w-0 flex-1 rounded-l-xl border border-r-0 bg-white px-3 text-sm outline-none focus:border-primary" /><button onClick={sendText} disabled={!text.trim() || processing || complete} className="grid h-11 w-11 place-items-center rounded-r-xl bg-slate-900 text-white disabled:opacity-40"><Send className="h-4 w-4" /></button></div></div></footer>
      </section>
      <aside className="space-y-4"><section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="flex items-center gap-2 font-bold"><FileCheck2 className="h-5 w-5 text-primary" /> Informations recueillies</h2><div className="mt-4 space-y-1">{Object.entries(data).filter(([key,value]) => value !== null && value !== undefined && !["firstname","lastname"].includes(key)).map(([key,value]) => <div key={key} className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 text-xs"><span className="text-muted-foreground">{LABELS[key] ?? key.replaceAll("_", " ")}</span><strong className="max-w-[55%] text-right">{typeof value === "boolean" ? (value ? "Oui" : "Non") : String(value)}</strong></div>)}{Object.keys(data).length === 0 && <p className="py-5 text-center text-xs text-muted-foreground">Les informations apparaîtront ici.</p>}</div></section>{complete && <section className="rounded-2xl border border-emerald-200 bg-emerald-50 p-5"><div className="flex items-center gap-2 font-bold text-emerald-800"><Check className="h-5 w-5" /> Recueil terminé</div><p className="mt-2 text-xs leading-5 text-emerald-700">Le dossier restera soumis à une validation humaine.</p>{savedClaim ? <p className="mt-4 rounded-xl bg-white p-3 text-xs font-semibold text-emerald-800">Dossier créé : {savedClaim}</p> : <button onClick={save} disabled={processing} className="mt-4 inline-flex h-10 w-full items-center justify-center gap-2 rounded-xl bg-emerald-700 text-sm font-bold text-white"><FileCheck2 className="h-4 w-4" /> Créer le dossier</button>}</section>}</aside>
    </div>
  </div>;
}
