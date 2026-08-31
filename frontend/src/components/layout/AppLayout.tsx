import { Outlet } from "@tanstack/react-router";
import { Sidebar } from "@/components/layout/Sidebar";
import { Bell, CircleUserRound, Search } from "lucide-react";

export function AppLayout() {
  return (
    <div className="flex h-screen w-full overflow-hidden bg-slate-50">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-16 shrink-0 items-center justify-between border-b border-slate-200/80 bg-white/90 px-7 backdrop-blur">
          <div className="relative hidden w-full max-w-sm md:block">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
            <input aria-label="Recherche rapide" placeholder="Rechercher un dossier…" className="h-10 w-full rounded-xl border border-slate-200 bg-slate-50 pl-10 pr-4 text-sm outline-none transition focus:border-primary/40 focus:bg-white focus:ring-4 focus:ring-primary/5" />
          </div>
          <div className="ml-auto flex items-center gap-3">
            <button aria-label="Notifications" className="grid h-10 w-10 place-items-center rounded-xl border border-slate-200 bg-white text-slate-500 transition hover:bg-slate-50"><Bell className="h-4 w-4" /></button>
            <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2">
              <CircleUserRound className="h-5 w-5 text-primary" /><div className="hidden sm:block"><p className="text-xs font-semibold leading-none">Agent démo</p><p className="mt-1 text-[10px] text-muted-foreground">Centre d’assistance</p></div>
            </div>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto max-w-[90rem] px-5 py-6 lg:px-8 lg:py-8"><Outlet /></div>
        </main>
      </div>
    </div>
  );
}
