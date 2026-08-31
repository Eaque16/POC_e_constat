import { Link, useRouterState } from "@tanstack/react-router";
import { navGroups } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { Headphones, ShieldCheck } from "lucide-react";

export function Sidebar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });

  return (
    <aside className="flex h-screen w-[17.5rem] shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground shadow-2xl shadow-slate-950/10">
      <div className="border-b border-sidebar-border px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="grid h-10 w-10 place-items-center rounded-xl bg-sidebar-primary text-sidebar-primary-foreground shadow-lg shadow-blue-950/20">
            <Headphones className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate text-[11px] font-semibold uppercase tracking-[0.18em] text-sidebar-foreground/55">ASA-CI Technologie</p>
            <p className="truncate text-base font-bold text-white">E-Constat IA</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-5">
        {navGroups.map((group) => (
          <div key={group.label}>
            <p className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-sidebar-foreground/40">{group.label}</p>
            <div className="space-y-1">
              {group.items.map(({ label, path, icon: Icon }) => {
                const isActive = path === "/" ? pathname === "/" : pathname.startsWith(path);
                return (
                  <Link key={path} to={path} className={cn(
                    "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200",
                    isActive
                      ? "bg-sidebar-primary text-sidebar-primary-foreground shadow-lg shadow-blue-950/20"
                      : "text-sidebar-foreground/72 hover:translate-x-0.5 hover:bg-sidebar-accent hover:text-white"
                  )}>
                    <Icon className="h-[18px] w-[18px] shrink-0" />
                    <span>{label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>

      <div className="border-t border-sidebar-border p-4">
        <div className="flex items-center gap-3 rounded-xl bg-sidebar-accent/70 p-3">
          <ShieldCheck className="h-5 w-5 text-emerald-400" />
          <div><p className="text-xs font-semibold text-white">Système opérationnel</p><p className="text-[10px] text-sidebar-foreground/50">Validation humaine active</p></div>
        </div>
      </div>
    </aside>
  );
}
