import { createRootRoute, createRoute, createRouter } from "@tanstack/react-router";
import { AppLayout } from "@/components/layout/AppLayout";
import { DashboardReal } from "@/pages/DashboardReal";
import { DataExplorerPage } from "@/pages/DataExplorer";
import {
  AppelsPage,
  AssistantIAPage,
  DossiersPage,
  SinistresPage,
  SantePage,
  StatistiquesPage,
  AgentsPage,
  ParametresPage,
} from "@/pages";

const rootRoute = createRootRoute({ component: AppLayout });

const routes = [
  createRoute({ getParentRoute: () => rootRoute, path: "/", component: DashboardReal }),
  createRoute({ getParentRoute: () => rootRoute, path: "/appels", component: AppelsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/assistant-ia", component: AssistantIAPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/dossiers", component: DossiersPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/sinistres", component: SinistresPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/donnees", component: DataExplorerPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/sante", component: SantePage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/statistiques", component: StatistiquesPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/agents", component: AgentsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: "/parametres", component: ParametresPage }),
];

const routeTree = rootRoute.addChildren(routes);
export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
