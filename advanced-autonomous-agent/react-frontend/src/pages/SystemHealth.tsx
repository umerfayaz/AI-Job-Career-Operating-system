import { Activity, Bot, HeartPulse, Workflow, Clock } from "lucide-react";
import { useSystemStatus } from "@/hooks/system_status";

export default function SystemHealth() {
  const { data, isLoading, error } = useSystemStatus();
  const formatLatency = (ms: number) => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
  
    return `${(ms / 1000).toFixed(1)}s`;
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-muted-foreground">
          Loading system metrics...
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-red-400">
          Failed to load system metrics
        </div>
      </div>
    );
  }

  const healthy = data.status === "healthy";

  const cards = [
    {
      title: "Career Analysis Time",
      value: `${formatLatency(data.frontend?.avg_latency_ms ?? 0)}`,
      latest_value: `${formatLatency(data.frontend?.latest_latency ?? 0)}`,
      fastest_value: `${formatLatency(data.frontend?.fastest_latency ?? 0)}`,
      slowest_value: `${formatLatency(data.frontend?.slowest_latency ?? 0)}`,
      success_value: `${data.frontend?.success_rate ?? 0}%`,
      icon: Activity,
      showMetrics: true,
    },
    {
      title: "Career Intelligence Time",
      value: `${formatLatency(data.autonomous?.avg_latency_ms ?? 0)}`,
      latest_value: `${formatLatency(data.autonomous?.latest_latency ?? 0)}`,
      fastest_value: `${formatLatency(data.autonomous?.fastest_latency ?? 0)}`,
      slowest_value: `${formatLatency(data.autonomous?.slowest_latency ?? 0)}`,
      success_value: `${data.autonomous?.success_rate ?? 0}%`,
      icon: Workflow,
      showMetrics: true,
    },
    {
      title: "Active Piplines",
      value: data.workflows?.active ?? 0,
      icon: Workflow,
      showMetrics: false,
    },
    {
      title: "Analaysis Modules",
      value: data.frontend?.agents?.length ?? 0,
      icon: Bot,
      showMetrics: false,
    },
    {
      title: "Intelligence Modules",
      value: data.autonomous?.agents?.length ?? 0,
      icon: Bot,
      showMetrics: false,
    },
  ];

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold tracking-tight">
          System Health
        </h1>

        <p className="text-muted-foreground mt-1">
          Real-time observability and workflow monitoring
        </p>
      </div>

      {/* Overall Status */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <HeartPulse
              className={`h-6 w-6 ${
                healthy ? "text-emerald-400" : "text-red-400"
              }`}
            />

            <div>
              <h2 className="font-semibold">
                System Status
              </h2>

              <p className="text-sm text-muted-foreground">
                Current platform health
              </p>
            </div>
          </div>

          <div
            className={`rounded-full px-3 py-1 text-sm font-medium ${
              healthy
                ? "bg-emerald-500/15 text-emerald-400"
                : "bg-red-500/15 text-red-400"
            }`}
          >
            {healthy ? "Healthy" : "Degraded"}
          </div>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;

          return (
            <div
              key={card.title}
              className="rounded-xl border border-border bg-card p-5"
            >
              <div className="flex items-center justify-between">
                <Icon className="h-5 w-5 text-primary" />

                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  Live
                </span>
              </div>

              <div className="mt-4">
                <p className="text-sm text-muted-foreground">
                  {card.title}
                </p>

                <p className="mt-1 text-3xl font-bold">
                  {card.value}
                </p>
                
                {card.latest_value && (
                <div className="mt-3 text-sm space-y-1">
                  <div>Latest: {card.latest_value}</div>
                  <div>Fastest: {card.fastest_value}</div>
                  <div>Slowest: {card.slowest_value}</div>
                  <div>Success: {card.success_value}</div>
                </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Workflow Health */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="mb-4 font-semibold">
             Career Analysis Engine
          </h3>

          <div className="space-y-3">
            <MetricRow
              label="Average Latency"
              value={`${formatLatency(
                data.frontend?.avg_latency_ms ?? 0
              )}`}
            />

            <MetricRow
              label="Latest Latency"
              value={`${formatLatency(data.frontend?.latest_latency ?? 0)}`}
            />

            <MetricRow
              label="Slowest Latency"
              value={`${formatLatency(data.frontend?.slowest_latency ?? 0)}`}
            />

            <MetricRow
              label="Fastest Latency"
              value={`${formatLatency(data.frontend?.fastest_latency ?? 0)}`}
            />

            <MetricRow
              label="Runs"
              value={data.frontend?.runs ?? 0}
            />

            <MetricRow
              label="Success Rate"
              value={`${data.frontend?.success_rate ?? 100}%`}
            />
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <h3 className="mb-4 font-semibold">
            Career Intelligence Engine
          </h3>

          <div className="space-y-3">
            <MetricRow
              label="Average Latency"
              value={`${formatLatency(
                data.autonomous?.avg_latency_ms ?? 0
              )}`}
            />

            <MetricRow
              label="Latest Latency"
              value={`${formatLatency(data.autonomous?.latest_latency ?? 0)}`}
            />

            <MetricRow
              label="Fastest Latency"
              value={`${formatLatency(data.autonomous?.fastest_latency ?? 0)}`}
            />

            <MetricRow
              label="Slowest Latency"
              value={`${formatLatency(data.autonomous?.slowest_latency ?? 0)}`}
            />

            <MetricRow
              label="Runs"
              value={data.autonomous?.runs ?? 0}
            />

            <MetricRow
              label="Success Rate"
              value={`${data.autonomous?.success_rate ?? 100}%`}
            />
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Clock className="h-4 w-4" />

          Last Updated:
          <span className="font-medium">
            {data.timestamp
              ? new Date(data.timestamp).toLocaleString()
              : "Unknown"}
          </span>
        </div>
      </div>
    </div>
  );
}

function MetricRow({
  label,
  value,
}: {
  label: string;
  value: string | number;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border pb-2">
      <span className="text-sm text-muted-foreground">
        {label}
      </span>

      <span className="font-medium">
        {value}
      </span>
    </div>
  );
}