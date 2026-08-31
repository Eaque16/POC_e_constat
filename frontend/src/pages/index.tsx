import { useState, useEffect, useCallback } from "react";
import { PagePlaceholder } from "@/components/layout/PagePlaceholder";
import { mockAgents } from "@/data/mockAgents";
import { mockCallStats } from "@/data/mockDashboard";
import { mockDossiers } from "@/data/mockDossiers";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { DossiersByStatusChart } from "@/components/dashboard/DossiersByStatusChart";
import { DossiersByTypeChart } from "@/components/dashboard/DossiersByTypeChart";
import { AgentList } from "@/components/agents/AgentList";
import { SinistreList } from "@/components/dossiers/SinistreList";
import { SinistreDetail } from "@/components/dossiers/SinistreDetail";
import { listSinistres } from "@/services/sinistres";
import type { SinistreResponse } from "@/types/api";
import { AssistantIAPanel } from "@/components/copilot/AssistantIAPanel";
import { RealCallWorkspace } from "@/components/call/RealCallWorkspace";

export function DashboardPage() {
  const validated = mockDossiers.filter((d) => d.statut === "Valide").length;
  const toVerify = mockDossiers.filter((d) => d.statut === "A verifier").length;
  const avgConfidence = Math.round(
    mockDossiers.reduce((sum, d) => sum + d.confiance, 0) / mockDossiers.length
  );

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{"Dashboard"}</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label={"Appels aujourd'hui"} value={mockCallStats.appelsAujourdhui} />
        <KpiCard label={"Appels en cours"} value={mockCallStats.appelsEnCours} accent="success" />
        <KpiCard label={"Dossiers cr\u00e9\u00e9s"} value={mockDossiers.length} />
        <KpiCard label={"\u00c0 v\u00e9rifier"} value={toVerify} accent="warning" />
        <KpiCard label={"Dossiers valid\u00e9s"} value={validated} accent="success" />
        <KpiCard label={"Temps moyen d'appel"} value={mockCallStats.tempsMoyenAppel} />
        <KpiCard label={"Taux classification IA"} value={`${avgConfidence}%`} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <DossiersByStatusChart dossiers={mockDossiers} />
        <DossiersByTypeChart dossiers={mockDossiers} />
      </div>
    </div>
  );
}

export function AppelsPage() {
  return <RealCallWorkspace />;
  /* const {
    state,
    simulateIncomingCall,
    answer,
    decline,
    toggleMute,
    toggleHold,
    hangUp,
    reset,
  } = useCallState();

  const [ivrDone, setIvrDone] = useState(false);
  const [extraQuestion, setExtraQuestion] = useState<string | null>(null);
  const [realAnalysis, setRealAnalysis] = useState<AnalysisResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const { start: startRecording, stopAndGetBlob, recordingError } = useCallRecording();

  useEffect(() => {
    if (state.status === "incoming") {
      setIvrDone(false);
      setExtraQuestion(null);
      setRealAnalysis(null);
      setAnalysisError(null);
    }
    if (state.status === "active") {
      void startRecording();
    }
  }, [state.status, startRecording]);

  const micActive = state.status === "active" && !state.isMuted && !state.isOnHold;
  const { turns, status, mode, micError } = useMicrophoneStream({ active: micActive });
  const { badges, suggestion, classification, extractedFields } = useCallAnalysis(
    turns,
    mockCaller.name,
    mockCaller.phone,
    mockCaller.contractNumber
  );

  const handleHangUp = useCallback(async () => {
    hangUp();
    setAnalyzing(true);
    setAnalysisError(null);
    try {
      const blob = await stopAndGetBlob();
      if (!blob || blob.size === 0) {
        setAnalysisError("Aucun audio enregistr\u00e9 - impossible d'analyser avec le backend reel.");
        return;
      }
      const result = await uploadAudioAndAnalyze(blob);
      setRealAnalysis(result);
    } catch (err) {
      if (err instanceof ApiError) {
        setAnalysisError(`Analyse backend \u00e9chou\u00e9e (${err.status}) : ${err.message}`);
      } else {
        setAnalysisError("Backend injoignable - v\u00e9rifie que le serveur tourne sur le port 8000.");
      }
    } finally {
      setAnalyzing(false);
    }
  }, [hangUp, stopAndGetBlob]);

  const handleReset = () => {
    setRealAnalysis(null);
    setAnalysisError(null);
    reset();
  };

  if (state.status === "idle") {
    return (
      <div className="flex h-[70vh] flex-col items-center justify-center gap-4">
        <p className="text-sm text-muted-foreground">{"Aucun appel en cours."}</p>
        <button
          onClick={simulateIncomingCall}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          {"Simuler un appel entrant"}
        </button>
      </div>
    );
  }

  if (state.status === "ended") {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <h2 className="text-xl font-bold">{"Appel termin\u00e9"}</h2>

        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold text-muted-foreground">{"Statut de l'analyse"}</h3>
          {analyzing && (
            <p className="mt-1 text-sm text-muted-foreground">
              {"Envoi de l'audio au backend et analyse en cours..."}
            </p>
          )}
          {!analyzing && analysisError && (
            <p className="mt-1 text-sm text-destructive">{analysisError}</p>
          )}
          {!analyzing && realAnalysis && (
            <p className="mt-1 text-sm text-success">
              {"Dossier cr\u00e9\u00e9 : "}
              {realAnalysis.reference ?? realAnalysis.sinistre_id}
            </p>
          )}
        </div>

        {realAnalysis ? (
          <SinistreDataView
            data={realAnalysis.donnees_structurees}
            infosManquantes={realAnalysis.infos_manquantes}
          />
        ) : (
          <>
            <CallClassification classification={classification} />
            <ExtractedInformation fields={extractedFields} />
          </>
        )}

        <button
          onClick={handleReset}
          className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          {"Retour au poste de travail"}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {state.status === "incoming" && !ivrDone && (
        <IVRSimulation onComplete={() => setIvrDone(true)} />
      )}

      {state.status === "incoming" && ivrDone && (
        <IncomingCallModal caller={mockCaller} onAnswer={answer} onDecline={decline} />
      )}

      {state.status === "active" && (
        <>
          <div className="flex items-center justify-between">
            <CallControls
              durationSeconds={state.durationSeconds}
              isMuted={state.isMuted}
              isOnHold={state.isOnHold}
              onToggleMute={toggleMute}
              onToggleHold={toggleHold}
              onHangUp={handleHangUp}
            />
          </div>
          <LiveCallStatus status={status} micError={micError ?? recordingError} />

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="space-y-4 lg:col-span-1">
              <CallerPanel caller={mockCaller} />
              <ClaimFolderMock folder={mockClaimFolder} />
            </div>
            <div className="lg:col-span-1">
              <LiveTranscript
                turns={turns}
                mode={mode}
                isListening={status === "listening" || status === "processing"}
              />
            </div>
            <div className="space-y-4 lg:col-span-1">
              <AIAssistant suggestion={suggestion} badges={badges} extraQuestion={extraQuestion} />
              <CallClassification classification={classification} />
              <ExtractedInformation fields={extractedFields} />
              <MissingInformation fields={extractedFields} onAskAbout={setExtraQuestion} />
            </div>
          </div>
        </>
      )}
    </div>
  ); */
}

export function AssistantIAPage() {
  return <AssistantIAPanel />;
}

export function DossiersPage() {
  const [sinistres, setSinistres] = useState<SinistreResponse[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const data = await listSinistres();
      setSinistres(data);
    } catch {
      setLoadError("Impossible de charger les dossiers depuis le backend.");
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const selected = sinistres?.find((s) => s.id === selectedId) ?? null;

  if (selected) {
    return (
      <SinistreDetail
        sinistre={selected}
        onBack={() => setSelectedId(null)}
        onUpdated={(updated) => {
          setSinistres((prev) =>
            prev ? prev.map((s) => (s.id === updated.id ? updated : s)) : prev
          );
        }}
      />
    );
  }

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{"Dossiers"}</h1>
      {loadError && <p className="text-sm text-destructive">{loadError}</p>}
      {!sinistres && !loadError && (
        <p className="text-sm text-muted-foreground">{"Chargement..."}</p>
      )}
      {sinistres && <SinistreList sinistres={sinistres} onSelect={setSelectedId} />}
    </div>
  );
}

export function SinistresPage() {
  return (
    <PagePlaceholder title="Sinistres" description={"Suivi des sinistres automobiles."} />
  );
}

export function SantePage() {
  return (
    <PagePlaceholder
      title={"Sant\u00e9"}
      description={"Suivi des dossiers assurance sant\u00e9."}
    />
  );
}

export function StatistiquesPage() {
  return (
    <PagePlaceholder
      title="Statistiques"
      description={"KPIs et graphiques - construit en Phase 6."}
    />
  );
}

export function AgentsPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{"Agents"}</h1>
      <AgentList agents={mockAgents} />
    </div>
  );
}

export function ParametresPage() {
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold text-foreground">{"Param\u00e8tres"}</h1>
      <div className="rounded-xl border border-border bg-card p-4">
        <dl className="space-y-1.5 text-sm">
          <div className="flex justify-between">
            <dt className="text-muted-foreground">{"URL API"}</dt>
            <dd className="font-mono text-xs">
              {import.meta.env.VITE_API_URL ?? "http://localhost:8000"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
}
