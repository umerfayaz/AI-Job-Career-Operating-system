import { useCallback, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useAuthContext } from "./context/AuthContext";
import type { Transition } from "framer-motion";
import { useSystemStatus } from "@/hooks/system_status";
import {
  Activity, AlertTriangle, Archive, BarChart3, Bell, Bookmark, BookOpen, Bot,
  Brain, ChevronDown, ChevronRight, CircleDot, Clock, Command, Cpu, CreditCard,
  Database, Download, FileSearch, FolderOpen, Gauge, GitBranch, GraduationCap,
  HeartPulse, InboxIcon, Key, Layers, LayoutDashboard, Lightbulb, LineChart,
  ListTodo, Lock, LogOut, Map, MemoryStick, MessageSquare, Network,
  PanelLeftClose, PanelLeftOpen, Play, Plug, Radio, RefreshCw, ScrollText,
  Search, Settings, Shield, ShieldCheck, SlidersHorizontal, Sparkles, Target,
  Telescope, TrendingDown, TrendingUp, User, UserCircle, Users, Wand2, Wrench,
  Zap, FlaskConical, Gavel, Eye
} from "lucide-react";

import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

// ─── Types ──────────────────────────────────────────────────────────────────

type NavItem = {
  id: string;
  label: string;
  icon: React.ElementType;
  badge?: string | number;
  badgeTone?: "live" | "new" | "count" | "warn";
};

type NavSection = {
  id: string;
  label: string;
  icon: React.ElementType;
  accent: string;         
  glow: string;            
  items: NavItem[];
};


const NAV_SECTIONS: NavSection[] = [
  {
    id: "command",
    label: "Command Center",
    icon: LayoutDashboard,
    accent: "text-cyan-400",
    glow: "0 0 24px -8px rgb(34 211 238 / 0.6)",
    items: [
      { id: "overview", label: "Overview", icon: LayoutDashboard },
      { id: "live-activity", label: "Live Activity", icon: Activity, badge: "LIVE", badgeTone: "live" },
      { id: "system-health", label: "System Health", icon: HeartPulse },
      { id: "real-time-events", label: "Real-Time Events", icon: Radio },
      { id: "active-operations", label: "Active Operations", icon: Layers },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence Layer",
    icon: Brain,
    accent: "text-purple-400",
    glow: "0 0 24px -8px rgb(192 132 252 / 0.6)",
    items: [
      { id: "career-intel", label: "Career Intelligence", icon: GraduationCap },
      { id: "skill-intel", label: "Skill Intelligence", icon: Lightbulb },
      { id: "market-analysis", label: "Market Analysis", icon: TrendingUp },
      { id: "resume-understanding", label: "Resume Understanding", icon: FileSearch },
      { id: "predictive-insights", label: "Predictive Insights", icon: Telescope },
      { id: "ai-recommendations", label: "AI Recommendations", icon: Wand2, badge: "NEW", badgeTone: "new" },
      { id: "reasoning-engine", label: "Reasoning Engine", icon: Brain },
    ],
  },
  {
    id: "agents",
    label: "Agent System",
    icon: Bot,
    accent: "text-rose-400",
    glow: "0 0 24px -8px rgb(251 113 133 / 0.6)",
    items: [
      { id: "agent-registry", label: "Agent Registry", icon: Bot },
      { id: "active-agents", label: "Active Agents", icon: CircleDot, badge: 7, badgeTone: "count" },
      { id: "agent-comms", label: "Agent Communication", icon: MessageSquare },
      { id: "agent-memory", label: "Agent Memory", icon: MemoryStick },
      { id: "agent-tasks", label: "Agent Tasks", icon: ListTodo },
      { id: "autonomous-decisions", label: "Autonomous Decisions", icon: GitBranch },
      { id: "coordination", label: "Coordination Layer", icon: Network },
      { id: "agent-sandbox", label: "Agent Sandbox", icon: FlaskConical, badge: "BETA", badgeTone: "new" },
    ],
  },
  {
    id: "workflow",
    label: "Workflow Engine",
    icon: Play,
    accent: "text-amber-400",
    glow: "0 0 24px -8px rgb(251 191 36 / 0.6)",
    items: [
      { id: "running-workflows", label: "Running Workflows", icon: Play, badge: 2, badgeTone: "count" },
      { id: "workflow-builder", label: "Workflow Builder", icon: Wrench },
      { id: "exec-history", label: "Execution History", icon: Clock },
      { id: "event-triggers", label: "Event Triggers", icon: Zap },
      { id: "auto-loops", label: "Autonomous Loops", icon: RefreshCw },
      { id: "queue", label: "Queue Management", icon: InboxIcon },
      { id: "failure-recovery", label: "Failure Recovery", icon: AlertTriangle, badge: 1, badgeTone: "warn" },
    ],
  },
  {
    id: "Subscription",
    label: "Plans & Billing",
    icon: CreditCard,
    accent: "text-fuchsia-400",
    glow: "0 0 24px -8px rgb(232 121 249 / 0.6)",
    items: [
      { id: "upgrade-plan", label: "Upgrade Plan", icon: CreditCard },
    ],
  },
  {
    id: "analytics",
    label: "Analytics & Reports",
    icon: BarChart3,
    accent: "text-emerald-400",
    glow: "0 0 24px -8px rgb(52 211 153 / 0.6)",
    items: [
      { id: "generated-reports", label: "Generated Reports", icon: BarChart3 },
      { id: "user-analytics", label: "User Analytics", icon: Users },
      { id: "performance", label: "Performance Metrics", icon: Gauge },
      { id: "ai-accuracy", label: "AI Accuracy", icon: Target },
      { id: "hiring-insights", label: "Hiring Insights", icon: TrendingDown },
      { id: "trends", label: "Trends", icon: LineChart },
      { id: "export", label: "Export Center", icon: Download },
    ],
  },
  {
    id: "knowledge",
    label: "Knowledge & Memory",
    icon: Database,
    accent: "text-sky-400",
    glow: "0 0 24px -8px rgb(56 189 248 / 0.6)",
    items: [
      { id: "vector-memory", label: "Vector Memory", icon: Database },
      { id: "user-context", label: "User Context", icon: UserCircle },
      { id: "retrieval", label: "Retrieval Engine", icon: Search },
      { id: "knowledge-base", label: "Knowledge Base", icon: BookOpen },
      { id: "embedded-data", label: "Embedded Data", icon: Cpu },
      { id: "session-memory", label: "Session Memory", icon: Clock },
      { id: "learning-store", label: "Learning Store", icon: Archive },
    ],
  },
  {
    id: "governance",
    label: "AI Governance",
    icon: ShieldCheck,
    accent: "text-indigo-400",
    glow: "0 0 24px -8px rgb(129 140 248 / 0.6)",
    items: [
      { id: "guardrails", label: "Guardrails", icon: Shield },
      { id: "policies", label: "Policies", icon: Gavel },
      { id: "audit-trail", label: "Audit Trail", icon: ScrollText },
      { id: "bias-monitor", label: "Bias Monitoring", icon: Eye },
      { id: "compliance", label: "Compliance", icon: ShieldCheck },
    ],
  },
  {
    id: "user",
    label: "User Space",
    icon: User,
    accent: "text-teal-400",
    glow: "0 0 24px -8px rgb(45 212 191 / 0.6)",
    items: [
      { id: "profile", label: "Profile", icon: User },
      { id: "saved-jobs", label: "Saved Jobs", icon: Bookmark },
      { id: "career-paths", label: "Career Paths", icon: Map },
      { id: "documents", label: "Documents", icon: FolderOpen },
      { id: "notifications", label: "Notifications", icon: Bell, badge: 3, badgeTone: "count" },
      { id: "preferences", label: "Preferences", icon: SlidersHorizontal },
    ],
  },
  {
    id: "system",
    label: "System Controls",
    icon: Settings,
    accent: "text-zinc-300",
    glow: "0 0 24px -8px rgb(212 212 216 / 0.4)",
    items: [
      { id: "api", label: "API Management", icon: Key },
      { id: "integrations", label: "Integrations", icon: Plug },
      { id: "security", label: "Security", icon: Shield },
      { id: "auth", label: "Authentication", icon: Lock },
      { id: "billing", label: "Billing", icon: CreditCard },
      { id: "settings", label: "Settings", icon: Settings },
      { id: "system-logs", label: "System Logs", icon: ScrollText },
    ],
  },
];

export type ActiveSelection = { group: string; item: string };

// ─── Badge ──────────────────────────────────────────────────────────────────

function Pill({ tone, children }: { tone: NavItem["badgeTone"]; children: React.ReactNode }) {
  const styles: Record<NonNullable<NavItem["badgeTone"]>, string> = {
    live: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30 shadow-[0_0_8px_-2px_rgb(16_185_129/0.6)]",
    new: "bg-violet-500/15 text-violet-300 border-violet-500/30",
    count: "bg-primary/15 text-primary border-primary/30",
    warn: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  };
  const tk = tone ?? "count";
  return (
    <span
      className={`ml-auto inline-flex h-[18px] min-w-[20px] items-center justify-center rounded-full border px-1.5 text-[10px] font-semibold tracking-wide ${styles[tk]} ${tk === "live" ? "animate-pulse" : ""}`}
    >
      {children}
    </span>
  );
}

// ─── Section row ────────────────────────────────────────────────────────────

function SectionRow({
  section,
  isOpen,
  active,
  onToggle,
  onSelect,
}: {
  section: NavSection;
  isOpen: boolean;
  active: ActiveSelection;
  onToggle: () => void;
  onSelect: (sel: ActiveSelection) => void;
}) {
  const Icon = section.icon;
  const hasActive = active.group === section.label;

  return (
    <div className="px-2">
      <button
        type="button"
        onClick={onToggle}
        className={`group relative flex h-9 w-full items-center gap-2.5 rounded-lg px-2 text-[13px] font-medium transition-colors duration-200 ${
          hasActive
            ? "bg-white/[0.04] text-white"
            : "text-white/65 hover:bg-white/[0.04] hover:text-white"
        }`}
      >
        {/* active rail */}
        <span
          className={`absolute left-0 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full transition-all duration-300 ${
            hasActive ? `${section.accent.replace("text-", "bg-")} opacity-100` : "opacity-0"
          }`}
        />
        <span
          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-all duration-200 ${
            hasActive
              ? `bg-white/[0.06] ${section.accent}`
              : "text-white/55 group-hover:text-white/85"
          }`}
        >
          <Icon className="h-3.5 w-3.5" />
        </span>
        <span className="flex-1 truncate text-left">{section.label}</span>
        <motion.span
          animate={{ rotate: isOpen ? 90 : 0 }}
          transition={{ duration: 0.2, ease: "easeOut" }}
          className="text-white/35 group-hover:text-white/70"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {isOpen && (
          <motion.div
            key="content"
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{
              height: { duration: 0.28, ease: [0.22, 1, 0.36, 1] },
              opacity: { duration: 0.18, ease: "easeOut" },
            }}
            className="overflow-hidden"
          >
            <div className="relative ml-[18px] mt-1 space-y-0.5 border-l border-white/[0.06] pl-2 pb-1">
              {section.items.map((item, idx) => {
                const ItemIcon = item.icon;
                const isActive =
                  active.group === section.label && active.item === item.label;
                return (
                  <motion.button
                    key={item.id}
                    type="button"
                    onClick={() => onSelect({ group: section.label, item: item.label })}
                    initial={{ opacity: 0, x: -6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.18, delay: idx * 0.02, ease: "easeOut" }}
                    className={`group relative flex w-full items-center gap-2.5 rounded-md px-2.5 py-1.5 text-left text-[12.5px] transition-colors duration-150 ${
                      isActive
                        ? `bg-white/[0.05] ${section.accent}`
                        : "text-white/50 hover:bg-white/[0.035] hover:text-white/90"
                    }`}
                  >
                    {isActive && (
                      <motion.span
                        layoutId={`active-dot-${section.id}`}
                        className={`absolute -left-[10px] top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full ${section.accent.replace(
                          "text-",
                          "bg-",
                        )}`}
                        style={{ boxShadow: section.glow }}
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                    <ItemIcon className="h-3.5 w-3.5 shrink-0 opacity-80" />
                    <span className="flex-1 truncate">{item.label}</span>
                    {item.badge !== undefined && <Pill tone={item.badgeTone}>{item.badge}</Pill>}
                  </motion.button>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// ─── Main Sidebar ───────────────────────────────────────────────────────────

interface AppSidebarProps {
    active: ActiveSelection;
    onSelect: (sel: ActiveSelection) => void;
    expanded: boolean;
    setExpanded: React.Dispatch<React.SetStateAction<boolean>>;
    onLogout?: () => void;
}

export function AppSidebar({
  active,
  onSelect,
  expanded,
  setExpanded,
  onLogout,
}: AppSidebarProps) {

  const {user, loading} = useAuthContext();
  const userName =  user?.name ?? "Guest";
  const userEmail = user?.email?? "";
  const { data } = useSystemStatus();
  const [openSections, setOpenSections] = useState<Set<string>>(
    () => new Set([NAV_SECTIONS.find((s) => s.label === active.group)?.id ?? "command"]),
  );
  const [hovered, setHovered] = useState<string | null>(null);
  const formatLatency = (ms: number) => {
    if (ms < 1000) return `${Math.round(ms)}ms`;
  
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const toggleSection = useCallback((id: string) => {
    setOpenSections((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const expandAndOpen = useCallback((id: string) => {
    setExpanded(true);
    setOpenSections((p) => new Set([...p, id]));
  }, []);

  const  sidebarTransition: Transition = {
    type: "spring",
    stiffness: 120,
    damping: 20
  }

  return (
    <motion.aside
      layout
      initial={false}
      animate={{ width: expanded ? 280 : 64 }}
      transition={sidebarTransition}
      className="
        fixed lg:relative
        left-0 top-0 z-[60]
        flex h-screen shrink-0 flex-col
        border-r border-sidebar-border
        bg-sidebar text-sidebar-foreground
      "
      style={{
        backgroundImage:
          "radial-gradient(120% 60% at 50% 0%, rgb(99 102 241 / 0.10), transparent 60%)",
      }}
    >
      {/* top edge glow */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent" />

      {/* ─── HEADER ─────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 px-3 pb-3 pt-4">
        <div className="relative flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-primary via-violet-500 to-fuchsia-500 shadow-[0_8px_24px_-8px_rgb(139_92_246/0.7)]">
          <Sparkles className="h-4 w-4 text-white" />
          <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-emerald-400 ring-2 ring-[var(--color-sidebar)]" />
        </div>
        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -6 }}
              transition={{ duration: 0.2 }}
              className="min-w-0 flex-1"
            >
              <div className="truncate text-sm font-semibold tracking-tight text-white">
                AutoAgent <span className="text-primary">OS</span>
              </div>
              <div className="truncate text-[10px] uppercase tracking-[0.18em] text-white/40">
                Intelligence Platform
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-white/40 transition-all duration-200 hover:bg-white/[0.06] hover:text-white/90 active:scale-95"
          title={expanded ? "Collapse" : "Expand"}
        >
          {expanded ? <PanelLeftClose className="h-3.5 w-3.5" /> : <PanelLeftOpen className="h-3.5 w-3.5" />}
        </button>
      </div>

      {/* ─── SEARCH ─────────────────────────────────────────────── */}
      <AnimatePresence initial={false}>
        {expanded && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden px-3 pb-3"
          >
            <button
              type="button"
              className="group flex w-full items-center gap-2 rounded-lg border border-white/[0.06] bg-white/[0.025] px-2.5 py-1.5 text-left text-xs text-white/45 transition-all duration-200 hover:border-white/[0.12] hover:bg-white/[0.05] hover:text-white/80"
            >
              <Search className="h-3.5 w-3.5" />
              <span className="flex-1 truncate">Quick search or command…</span>
              <kbd className="flex items-center gap-0.5 rounded border border-white/[0.08] bg-white/[0.03] px-1 font-mono text-[10px] text-white/50">
                <Command className="h-2.5 w-2.5" />K
              </kbd>
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ─── NAV ────────────────────────────────────────────────── */}
      <nav className="scrollbar-thin flex-1 overflow-y-auto overflow-x-hidden py-1">
        {expanded ? (
          <div className="space-y-0.5 pb-2">
            <div className="px-4 pb-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.22em] text-white/30">
              Platform
            </div>
            {NAV_SECTIONS.map((section) => (
              <SectionRow
                key={section.id}
                section={section}
                isOpen={openSections.has(section.id)}
                active={active}
                onToggle={() => toggleSection(section.id)}
                onSelect={onSelect}
              />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1 py-2">
            {NAV_SECTIONS.map((sec) => {
              const Icon = sec.icon;
              const hasActive = active.group === sec.label;
              return (
                <div
                  key={sec.id}
                  className="relative"
                  onMouseEnter={() => setHovered(sec.id)}
                  onMouseLeave={() => setHovered(null)}
                >
                  <button
                    type="button"
                    onClick={() => expandAndOpen(sec.id)}
                    className={`relative flex h-10 w-10 items-center justify-center rounded-xl transition-all duration-200 active:scale-95 ${
                      hasActive
                        ? `bg-white/[0.06] ${sec.accent}`
                        : "text-white/45 hover:bg-white/[0.05] hover:text-white"
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {hasActive && (
                      <motion.span
                        layoutId="collapsed-active"
                        className={`absolute -left-1 top-1/2 h-5 w-[2px] -translate-y-1/2 rounded-full ${sec.accent.replace(
                          "text-",
                          "bg-",
                        )}`}
                        transition={{ type: "spring", stiffness: 380, damping: 30 }}
                      />
                    )}
                  </button>
                  <AnimatePresence>
                    {hovered === sec.id && (
                      <motion.div
                        initial={{ opacity: 0, x: -4 }}
                        animate={{ opacity: 1, x: 0 }}
                        exit={{ opacity: 0, x: -4 }}
                        transition={{ duration: 0.15 }}
                        className="pointer-events-none absolute left-full top-1/2 z-50 ml-2 -translate-y-1/2 whitespace-nowrap rounded-md border border-white/10 bg-zinc-900/95 px-2.5 py-1 text-xs font-medium text-white shadow-xl backdrop-blur"
                      >
                        {sec.label}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        )}
      </nav>

      {/* ─── FOOTER ─────────────────────────────────────────────── */}
      <div className="border-t border-white/[0.06] p-2">
        <AnimatePresence initial={false}>
          {expanded && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.22 }}
              className="overflow-hidden"
            >
              <div className="mb-2 rounded-lg border border-white/[0.06] bg-gradient-to-br from-primary/10 via-white/[0.02] to-transparent p-2.5">
                {/* Header */}
                <div className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-primary">
                 <Activity className="h-3 w-3" />
                 System Status
                </div>
                {/* Status Row */}
                <div className="mt-1 flex items-center justify-between">
                 <span className="text-xs text-white/85">
                  {data?.status ?? "loading"}
                 </span>

                  <span className="relative flex h-2 w-2">
                   <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                   <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
                  </span>
                </div>

                {/* Metrics */}
                <div className="mt-1 space-y-1 text-[10px] text-white/45">

                  <div className="flex justify-between">
                    <span>Career Engine</span>
                    <span>{formatLatency(data?.frontend?.avg_latency_ms ?? 0)}</span>
                  </div>

                  <div className="flex justify-between">
                    <span>Inelligence Engine</span>
                    <span>{formatLatency(data?.autonomous?.avg_latency_ms ?? 0)}</span>
                  </div>

                  <div className="flex justify-between">
                   <span>Active Workflows</span>
                   <span>{data?.workflows?.active ?? 0}</span>
                  </div>

                 </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <button
              type="button"
              className="flex w-full items-center gap-2 rounded-lg p-1.5 text-left transition-colors duration-200 hover:bg-white/[0.05]"
            >
              <div className="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-fuchsia-500 text-xs font-semibold text-white ring-2 ring-primary/20">
                {userName.charAt(0)}
                <span className="absolute -bottom-0.5 -right-0.5 h-2 w-2 rounded-full bg-emerald-400 ring-2 ring-[var(--color-sidebar)]" />
              </div>
              <AnimatePresence initial={false}>
                {expanded && (
                  <motion.div
                    initial={{ opacity: 0, x: -4 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -4 }}
                    transition={{ duration: 0.18 }}
                    className="flex min-w-0 flex-1 items-center gap-2"
                  >
                    <div className="space-y-1">
                        {loading ? (
                            <>
                            <div className="h-3 w-24 animate-pulse rounded bg-white/10" />
                            <div className="h-2 w-32 animate-pulse rounded bg-white/5" />
                            </>
                        ) : (
                            <>
                            <div className="truncate text-xs font-medium text-white">
                                {userName}
                            </div>
                            <div className="truncate text-[10px] text-white/45">
                                {userEmail}
                            </div>
                        </>
                        )}
                    </div>
                    <ChevronDown className="h-3.5 w-3.5 text-white/35" />
                  </motion.div>
                )}
              </AnimatePresence>
            </button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" side="top" className="w-56 z-[9999]">
            <DropdownMenuLabel>My Account</DropdownMenuLabel>
            <DropdownMenuItem><User className="mr-2 h-4 w-4" /> Profile</DropdownMenuItem>
            <DropdownMenuItem><Settings className="mr-2 h-4 w-4" /> Settings</DropdownMenuItem>
            <DropdownMenuItem><Shield className="mr-2 h-4 w-4" /> Security</DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={onLogout} className="text-destructive focus:text-destructive">
              <LogOut className="mr-2 h-4 w-4" /> Log out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </motion.aside>
  );
}

export default AppSidebar;