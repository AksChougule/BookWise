import { useCallback, useState } from "react";

import { getHealthApi, getHealthRoot, getMetrics } from "../api/admin";
import { ApiError } from "../api/client";
import { JsonViewer } from "../components/JsonViewer";

type PanelState = {
  loading: boolean;
  error: string | null;
  data: unknown;
};

const initialState: PanelState = { loading: false, error: null, data: null };

function toErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return `Request failed (${error.status}): ${error.message}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function AdminPanel() {
  const [healthRoot, setHealthRoot] = useState<PanelState>(initialState);
  const [healthApi, setHealthApi] = useState<PanelState>(initialState);
  const [metrics, setMetrics] = useState<PanelState>(initialState);

  const fetchSection = useCallback(
    async (
      setter: React.Dispatch<React.SetStateAction<PanelState>>,
      request: () => Promise<unknown>,
    ) => {
      setter({ loading: true, error: null, data: null });
      try {
        const data = await request();
        setter({ loading: false, error: null, data });
      } catch (error) {
        setter({ loading: false, error: toErrorMessage(error), data: null });
      }
    },
    [],
  );

  const fetchAll = useCallback(async () => {
    await Promise.all([
      fetchSection(setHealthRoot, getHealthRoot),
      fetchSection(setHealthApi, getHealthApi),
      fetchSection(setMetrics, getMetrics),
    ]);
  }, [fetchSection]);

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">Admin Panel</h1>
          <p className="text-secondary">Operational backend checks and metrics.</p>
        </div>
        <button className="btn" onClick={fetchAll}>
          Fetch all
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <AdminCard
          title="Health"
          endpoint="/health"
          state={healthRoot}
          onFetch={() => fetchSection(setHealthRoot, getHealthRoot)}
        />
        <AdminCard
          title="API Health"
          endpoint="/api/health"
          state={healthApi}
          onFetch={() => fetchSection(setHealthApi, getHealthApi)}
        />
        <AdminCard
          title="Metrics"
          endpoint="/metrics"
          state={metrics}
          onFetch={() => fetchSection(setMetrics, getMetrics)}
          defaultCollapsed
        />
      </div>
    </section>
  );
}

type AdminCardProps = {
  title: string;
  endpoint: string;
  state: PanelState;
  onFetch: () => void;
  defaultCollapsed?: boolean;
};

function AdminCard({ title, endpoint, state, onFetch, defaultCollapsed = false }: AdminCardProps) {
  return (
    <article className="flex min-h-[260px] flex-col rounded-xl border border-app bg-surface p-4">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{title}</h2>
          <p className="text-sm text-secondary">{endpoint}</p>
        </div>
        <button className="btn" onClick={onFetch} disabled={state.loading}>
          {state.loading ? "Loading..." : "Refresh"}
        </button>
      </div>

      {state.error && <p className="rounded-md border border-red-400/50 bg-red-50 p-2 text-sm text-red-700">{state.error}</p>}
      {!state.error && state.data !== null && (
        <JsonViewer data={state.data} title={`${title} response`} defaultCollapsed={defaultCollapsed} />
      )}
      {!state.error && state.data === null && !state.loading && (
        <p className="text-sm text-secondary">No data loaded yet.</p>
      )}
    </article>
  );
}
