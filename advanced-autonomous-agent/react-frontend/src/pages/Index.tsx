import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useAuth } from '@/hooks/useAuth';
import {ActiveSelection, AppSidebar} from '@/components/app-sidebar'
import SystemHealth from './SystemHealth';
import SubscriptionPage from '@/components/subscription';
import { motion, AnimatePresence, useScroll, useTransform, useInView } from 'framer-motion';
import { SiWhatsapp, SiGmail, SiSlack, SiTelegram } from "react-icons/si";
import { 
  Upload, FileText, Briefcase, CheckCircle, Loader, Brain, MessageSquare, 
  Shield, Terminal, Sparkles, X, Activity, Download, Zap, Server, Database, 
  Cpu, Network, ArrowRight,Rocket, Target, BarChart3, Clock, Quote, 
  Star, Bell, Lock

} from 'lucide-react';

const FEATURES = [
  {
    icon: Brain,
    title: "Autonomous Multi-Agent Intelligence",
    desc: "A coordinated AI workforce powered by specialized agents that reason, plan, execute, and continuously optimize your entire job search lifecycle.",
    gradient: "from-blue-500 to-cyan-500",
  },
  {
    icon: Target,
    title: "Strategic Career Intelligence",
    desc: "Combines hybrid retrieval, RAG, BM25, semantic search, and AI reranking to discover and prioritize the highest-value career opportunities.",
    gradient: "from-purple-500 to-pink-500",
  },
  {
    icon: Rocket,
    title: "Continuous Career Automation",
    desc: "Runs autonomous workflows 24/7 to discover jobs, refine strategies, track applications, and improve outcomes without constant user intervention.",
    gradient: "from-indigo-500 to-violet-500",
  },
  {
    icon: BarChart3,
    title: "Decision Intelligence & Analytics",
    desc: "Every workflow, recommendation, and autonomous decision is analyzed, audited, and transformed into actionable career insights.",
    gradient: "from-green-500 to-emerald-500",
  },
  {
    icon: Bell,
    title: "Application & Email Monitoring",
    desc: "Tracks submitted applications, monitors employer responses, detects interviews, and delivers real-time notifications across connected channels.",
    gradient: "from-orange-500 to-yellow-500",
  },
  {
    icon: Lock,
    title: "Enterprise AI Governance",
    desc: "Policy-driven execution with runtime governance, secure memory, human approval workflows, and auditable AI decision making.",
    gradient: "from-red-500 to-rose-500",
  },
];

const INTEGRATIONS = [
  { name: "Slack", icon: SiSlack, color: "#4A154B" },
  { name: "WhatsApp", icon: SiWhatsapp, color: "#25D366" },
  { name: "Pushover", icon: Bell, color: "#249DF1" },
  { name: "Gmail", icon: SiGmail, color: "#EA4335" },
  { name: "Telegram", icon: SiTelegram, color: "#0088CC" },
];

const TESTIMONIALS = [
  {
    name: "Sarah Chen",
    role: "Senior ML Engineer",
    company: "Hired at Anthropic",
    quote: "AutoAgent OS surfaced 3 roles I never would've found. The fit-score breakdown told me exactly what to fix in my resume.",
    avatar: "SC",
  },
  {
    name: "Marcus Rivera",
    role: "Backend Engineer",
    company: "Hired at Stripe",
    quote: "I set it up Sunday night, woke up to 12 ranked matches and a Slack ping for a Stripe role. Two weeks later I had the offer.",
    avatar: "MR",
  },
  {
    name: "Aisha Patel",
    role: "Product Designer",
    company: "Hired at Linear",
    quote: "The autonomous agents felt like a real recruiter — except faster, honest, and available at 2am.",
    avatar: "AP",
  },
];


const OverviewDashboard = () => (
  <div className="glass-panel p-8 text-center text-muted-foreground">
    <BarChart3 className="w-10 h-10 mx-auto mb-4 opacity-40" />
    <p className="font-semibold">Overview Dashboard</p>
  </div>
);

const LiveActivity = () => (
  <div className="glass-panel p-8 text-center text-muted-foreground">
    <Activity className="w-10 h-10 mx-auto mb-4 opacity-40" />
    <p className="font-semibold">Live Activity</p>
  </div>
);

const RealtimeEvents = () => (
  <div className="glass-panel p-8 text-center text-muted-foreground">
    <Zap className="w-10 h-10 mx-auto mb-4 opacity-40" />
    <p className="font-semibold">Real-Time Events</p>
  </div>
);

const ActiveOperations = () => (
  <div className="glass-panel p-8 text-center text-muted-foreground">
    <Cpu className="w-10 h-10 mx-auto mb-4 opacity-40" />
    <p className="font-semibold">Active Operations</p>
  </div>
);

const FeatureCard = ({ feature, index }: { feature: typeof FEATURES[0]; index: number }) => {
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, margin: "-50px" });
  const Icon = feature.icon;

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 40 }}
      animate={inView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.5, delay: index * 0.08 }}
      whileHover={{ y: -6, scale: 1.02 }}
      className="group relative min-h-[260px] p-7 rounded-2xl bg-card border border-border overflow-hidden cursor-pointer"
    >
      <div
        className={`absolute -inset-px rounded-2xl bg-gradient-to-br ${feature.gradient} opacity-0 group-hover:opacity-20 blur-xl transition-opacity duration-500`}
      />
      <div className="absolute inset-0 bg-gradient-to-br from-transparent via-transparent to-primary/5 opacity-0 group-hover:opacity-100 transition-opacity duration-500" />

      <div className="relative">
        <div className={`inline-flex p-3 rounded-xl bg-gradient-to-br ${feature.gradient} shadow-lg mb-5 group-hover:scale-110 transition-transform duration-300`}>
          <Icon className="w-6 h-6 text-white" />
        </div>
        <h3 className="text-xl font-bold mb-3 text-foreground group-hover:text-primary transition-colors">
          {feature.title}
        </h3>
        <p className="text-sm text-muted-foreground leading-relaxed">
          {feature.desc}
        </p>
        <div className="mt-5 flex items-center gap-2 text-xs font-medium text-primary opacity-0 group-hover:opacity-100 transition-opacity">
          Learn more <ArrowRight className="w-3 h-3" />
        </div>
      </div>
    </motion.div>
  );
};

const IntegrationsRow = () => {
  const doubled = [...INTEGRATIONS, ...INTEGRATIONS, ...INTEGRATIONS];

  return (
    <motion.div
      initial={{ opacity: 0 }}
      whileInView={{ opacity: 1 }}
      viewport={{ once: true }}
      className="mt-16 overflow-hidden"
    >
      {/* Heading */}
      <div className="text-center mb-8">
        <p className="text-xs uppercase tracking-widest text-muted-foreground mb-2">
          Integrated tools
        </p>

        <h3 className="text-2xl font-bold text-foreground">
          Push results everywhere you already work
        </h3>
      </div>

      {/* Sliding container */}
      <div className="relative w-full overflow-hidden">

        {/* Left fade */}
        <div className="absolute left-0 top-0 h-full w-24 bg-gradient-to-r from-background to-transparent z-10" />

        {/* Right fade */}
        <div className="absolute right-0 top-0 h-full w-24 bg-gradient-to-l from-background to-transparent z-10" />

        <motion.div
          className="flex gap-4 whitespace-nowrap"
          animate={{
            x: [0, -900],
          }}
          transition={{
            repeat: Infinity,
            repeatType: "loop",
            duration: 18,
            ease: "linear",

          }}
        >
          {doubled.map((tool, i) => {
            const Icon = tool.icon;

            return (
              <div
                key={i}
                className="group flex items-center gap-3 px-5 py-3 rounded-xl bg-card border border-border hover:border-primary/50 transition-all duration-300 cursor-pointer min-w-[180px] hover:-translate-y-1"
              >
                <div
                  className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg group-hover:scale-110 transition-transform duration-300"
                  style={{ backgroundColor: tool.color }}
                >
                  <Icon className="w-5 h-5 text-white" />
                </div>

                <span className="font-medium text-sm text-foreground group-hover:text-primary transition-colors">
                  {tool.name}
                </span>
              </div>
            );
          })}
        </motion.div>
      </div>
    </motion.div>
  );
};

const TestimonialCard = ({ t, index }: { t: typeof TESTIMONIALS[0]; index: number }) => (
  <motion.div
    initial={{ opacity: 0, y: 30 }}
    whileInView={{ opacity: 1, y: 0 }}
    viewport={{ once: true }}
    transition={{ duration: 0.5, delay: index * 0.1 }}
    whileHover={{ y: -4 }}
    className="relative p-7 rounded-2xl bg-card border border-border hover:border-primary/40 transition-colors group"
  >
    <Quote className="absolute top-5 right-5 w-8 h-8 text-primary/10 group-hover:text-primary/20 transition-colors" />
    <div className="flex gap-1 mb-4">
      {[...Array(5)].map((_, i) => (
        <Star key={i} className="w-4 h-4 fill-yellow-400 text-yellow-400" />
      ))}
    </div>
    <p className="text-sm text-foreground leading-relaxed mb-6 italic">
      &ldquo;{t.quote}&rdquo;
    </p>
    <div className="flex items-center gap-3">
      <div className="w-11 h-11 rounded-full bg-gradient-to-br from-primary to-purple-500 flex items-center justify-center text-white font-semibold text-sm">
        {t.avatar}
      </div>
      <div>
        <div className="font-semibold text-sm text-foreground">{t.name}</div>
        <div className="text-xs text-muted-foreground">
          {t.role} · <span className="text-primary">{t.company}</span>
        </div>
      </div>
    </div>
  </motion.div>
);

const PreChatShowcase = ({
  setActiveTab,

}:{
  setActiveTab: (tab: ActiveSelection) => void;
}) => (
  <div className="space-y-20 py-8">
    {/* Features */}
    <section>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
          <Sparkles className="w-3 h-3" /> What this tool does
        </div>
        <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
          A complete autonomous job-search OS
        </h2>
        <p className="text-muted-foreground max-w-2xl mx-auto">
          Six specialized AI agents work in parallel to find, score, and deliver opportunities tailored to you.
        </p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {FEATURES.map((f, i) => (
          <FeatureCard key={f.title} feature={f} index={i} />
        ))}
      </div>

      <IntegrationsRow />
    </section>

    {/* Testimonials */}
    <section>
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        className="text-center mb-12"
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium mb-4">
          <Star className="w-3 h-3" /> What people say
        </div>
        <h2 className="text-4xl md:text-5xl font-bold text-foreground mb-4">
          Hired by AutoAgent OS
        </h2>
        <p className="text-muted-foreground">Real stories from people the agents placed.</p>
      </motion.div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {TESTIMONIALS.map((t, i) => (
          <TestimonialCard key={t.name} t={t} index={i} />
        ))}
      </div>
    </section>

    {/* CTA */}
    <motion.section
      initial={{ opacity: 0, scale: 0.95 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true }}
      className="relative overflow-hidden rounded-3xl border border-border bg-gradient-to-br from-primary/10 via-purple-500/10 to-pink-500/10 p-12 text-center"
    >
      <div className="absolute inset-0 bg-grid-white/[0.02]" />
      <div className="relative">
        <h3 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
          Ready to start? Upload your resume.
        </h3>
        <p className="text-muted-foreground mb-6 max-w-xl mx-auto">
          Verify your email and watch the agents go to work in real-time.
        </p>
        <motion.button
          initial={{ opacity: 0, scale: 0.95 }}
          whileInView={{ opacity: 1, scale: 1 }}
          viewport={{ once: true }}
          onClick={() => setActiveTab({
            group: "Command Center",
            item: "Job Matching"
          })}
          
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-white text-sm font-semibold shadow-lg shadow-primary/20
                    hover:shadow-2xl hover:shadow-primary/40 hover:scale-105 hover:-translate-y-1 active:scale-95 transition-all duration-300
                    border border-white/10 hover:border-white/20 relative overflow-hidden group"
        >
          <ArrowRight className="w-4 h-4" />
          Switch to the Job Matching tab above
        </motion.button>
      </div>
    </motion.section>
  </div>
);

// Typing effect hook for Claude/ChatGPT-like streaming
const useTypingEffect = (text: string, speed: number = 20, isActive: boolean = true) => {
  const [displayedText, setDisplayedText] = useState('');
  const [isComplete, setIsComplete] = useState(false);
  const indexRef = useRef(0);

  useEffect(() => {
    if (!isActive) {
      setDisplayedText(text);
      setIsComplete(true);
      return;
    }
  
    let index = 0;
    setDisplayedText('');
    setIsComplete(false);
  
    const timer = setInterval(() => {
      if (indexRef.current < text.length) {
        setDisplayedText((prev) => prev + text[indexRef.current]);
        indexRef.current++;
      } else {
        setIsComplete(true);
        clearInterval(timer);
      }
    }, speed);
  
    return () => {
      clearInterval(timer); 
    };
  }, [text, speed, isActive]);

  return { displayedText, isComplete };
};

// Animated counter component
const AnimatedCounter = ({ value, duration = 2000 }: { value: number; duration?: number }) => {
  const [count, setCount] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true });

  useEffect(() => {
    if (!isInView) return;
    
    const steps = 60;
    const increment = value / steps;
    let current = 0;
    
    const timer = setInterval(() => {
      current += increment;
      if (current >= value) {
        setCount(value);
        clearInterval(timer);
      } else {
        setCount(Math.floor(current));
      }
    }, duration / steps);

    return () => clearInterval(timer);
  }, [value, duration, isInView]);

  return <span ref={ref}>{count.toLocaleString()}</span>;
};

// Floating particles background
const ParticleBackground = () => {
  const [dimensions, setDimensions] = useState({width: 1000, height: 800});

  useEffect(() => {
    setDimensions({
    width: window.innerWidth,
    height: window.innerHeight
    });
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      {[...Array(20)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute w-1 h-1 bg-primary/30 rounded-full"
          initial={{
            x: Math.random() * dimensions.width,
            y: Math.random() * dimensions.height,
          }}
          animate={{
            y: [null, -100],
            opacity: [0, 1, 0],
          }}
          transition={{
            duration: Math.random() * 5 + 5,
            repeat: Infinity,
            repeatType: 'loop',
            delay: Math.random() * 5,
          }}
        />
      ))}
    </div>
  );
};

// Chat message with typing effect
const ChatMessage = ({ message, isNew }: { message: AgentDashboardChatItem; isNew: boolean }) => {
  const { displayedText, isComplete } = useTypingEffect(
    message.content,
    15,
    isNew && message.type === 'Autonomous_agent'
  );

  const getAgentIcon = (role: string) => {
    switch (role?.toLowerCase()) {
      case 'resume_agent': return <FileText className="w-4 h-4" />;
      case 'job_matcher_agent': return <Target className="w-4 h-4" />;
      case 'report_agent': return <BarChart3 className="w-4 h-4" />;
      case 'notification_agent': return <Zap className="w-4 h-4" />;
      default: return <Brain className="w-4 h-4" />;
    }
  };

  const getAgentColor = (role: string) => {
    switch (role?.toLowerCase()) {
      case 'resume_agent': return 'from-blue-500 to-cyan-500';
      case 'job_matcher_agent': return 'from-purple-500 to-pink-500';
      case 'report_agent': return 'from-green-500 to-emerald-500';
      case 'notification_agent': return 'from-orange-500 to-yellow-500';
      default: return 'from-primary to-secondary';
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.95 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.4, ease: 'easeOut' }}
      className="flex justify-start group"
    >
      <div className="max-w-[90%] relative">
        {/* Glow effect */}
        <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 to-secondary/20 rounded-2xl blur-lg opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        
        <div className="relative glass-panel p-4 hover:border-primary/30 transition-all duration-300">
          {/* Agent header */}
          <div className="flex items-center gap-3 mb-3">
            <motion.div 
              className={`w-8 h-8 rounded-lg bg-gradient-to-br ${getAgentColor(message.role)} flex items-center justify-center`}
              whileHover={{ scale: 1.1, rotate: 5 }}
              transition={{ type: 'spring', stiffness: 400 }}
            >
              {getAgentIcon(message.role)}
            </motion.div>
            <div className="flex-1">
              <span className="text-sm font-semibold gradient-text">
                {message.role || 'AI Assistant'}
              </span>
              {message.agent && (
                <span className="text-xs text-muted-foreground ml-2">• {message.agent}</span>
              )}
            </div>
            <Clock className="w-3 h-3 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {new Date(message.timestamp).toLocaleTimeString([], {
                hour: '2-digit',
                minute: '2-digit',
              })}
            </span>
          </div>
          
          {/* Message content with typing effect */}
          <div className={`chat-text leading-relaxed text-foreground/90 ${isNew && message.type === 'Autonomous_agent' && !isComplete ? "typing" : ""}`}>
            {isNew && message.type === 'Autonomous_agent' ? displayedText : message.content}
          </div>
        </div>
      </div>
    </motion.div>
  );
};

// Processing indicator
const ProcessingIndicator = () => (
  <motion.div
    initial={{ opacity: 0, y: 10 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: -10 }}
    className="flex justify-start"
  >
    <div className="glass-panel px-5 py-4">
      <div className="flex items-center gap-3">
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
          className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center"
        >
          <Cpu className="w-4 h-4 text-primary-foreground" />
        </motion.div>
        <div className="flex gap-1.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="w-2 h-2 bg-primary rounded-full"
              animate={{ scale: [1, 1.3, 1], opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.15 }}
            />
          ))}
        </div>
        <span className="text-sm text-muted-foreground ml-2">Agents processing...</span>
      </div>
    </div>
  </motion.div>
);

// Stat card with hover effects
const StatCard = ({ stat, index }: { stat: { label: string; value: number; icon: any }; index: number }) => {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      animate={isInView ? { opacity: 1, y: 0 } : {}}
      transition={{ duration: 0.6, delay: index * 0.1 }}
      whileHover={{ y: -8, scale: 1.02 }}
      className="group relative"
    >
      {/* Glow effect on hover */}
      <div className="absolute -inset-1 bg-gradient-to-r from-primary to-secondary rounded-2xl blur-xl opacity-0 group-hover:opacity-30 transition-opacity duration-500" />
      
      <div className="relative glass-panel p-8 overflow-hidden">
        {/* Background shimmer */}
        <div className="absolute inset-0 animate-shimmer opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
        
        <motion.div
          whileHover={{ rotate: 10, scale: 1.1 }}
          transition={{ type: 'spring', stiffness: 300 }}
          className="w-14 h-14 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center mx-auto mb-4"
        >
          <stat.icon className="w-7 h-7 text-primary-foreground" />
        </motion.div>
        
        <div className="text-4xl font-bold gradient-text mb-2">
          <AnimatedCounter value={stat.value} />
        </div>
        <div className="text-sm text-muted-foreground">{stat.label}</div>
      </div>
    </motion.div>
  );
};

// Tab button with animations
const TabButton = ({ tab, isActive, onClick }: { tab: any; isActive: boolean; onClick: () => void }) => (
  <motion.button
    onClick={onClick}
    whileHover={{ scale: 1.02 }}
    whileTap={{ scale: 0.98 }}
    className={`relative flex-1 flex items-center justify-center gap-3 px-6 py-4 rounded-xl font-semibold transition-all overflow-hidden ${
      isActive ? 'text-primary-foreground' : 'text-muted-foreground hover:text-foreground'
    }`}
  >
    {isActive && (
      <motion.div
        layoutId="activeTab"
        className="absolute inset-0 bg-gradient-to-r from-primary to-secondary"
        initial={false}
        transition={{ type: 'spring', stiffness: 500, damping: 35 }}
      />
    )}
    <span className="relative z-10 flex items-center gap-3">
      <tab.icon className="w-5 h-5" />
      {tab.label}
    </span>
  </motion.button>
);

type AgentDashboardChatItem = {
  id: number;
  type: string;
  role: string;
  content: string;
  timestamp: Date;
  isNew: boolean;
  agent?: string;
  done?: boolean;
};

// Main Dashboard Component
const AgentDashboard = () => {
  const { logout } = useAuth();
  const [activeTab, setActiveTab] = useState<ActiveSelection>({
    group: "Command Center",
    item: "Agent Progress"
  });

  const [taskId, setTaskId] = useState('');
  const [backendLogs, setBackendLogs] = useState<any[]>([]);
  const [showLogs, setShowLogs] = useState(false);
  const [reportUrl, setReportUrl] = useState('');
  const [wsConnected, setWsConnected] = useState(false);
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [showChat, setShowChat] = useState(false);
  const [chatMessages, setChatMessages] = useState<AgentDashboardChatItem[]>([
    {
      id: 1,
      type: 'Autonomous_agent',
      role: 'Career_agent',
      content: "Hello! I'm your AI Career Assistant. Upload your resume in the Job Matching tab to get started, and I'll guide you through the entire process here.",
      timestamp: new Date(),
      isNew: false
    }
  ]);
  const [isChatProcessing, setIsChatProcessing] = useState(false);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const [isThinking, setIsThinking] = useState(false);
  const [ThinkingMessage, setThinkingMessage] = useState("");
  const [currentStage, setCurrentStage] = useState("");
  const [currentAgent, setCurrentAgent] = useState<string | null>(null) 
  const pingref = useRef<NodeJS.Timeout | null>(null);
  const { scrollY } = useScroll();
  const headerOpacity = useTransform(scrollY, [0, 100], [0.8, 0.95]);
  const headerBlur = useTransform(scrollY, [0, 100], [10, 20]);
  const [logoutConfirming, setLogoutConfirming] = useState(false);
  const logoutTimerRef = useRef<NodeJS.Timeout |null>(null);
  const  [sidebarExpanded, setsidebarExpanded] = useState(false);

  const [backendStats, setBackendStats] = useState({
    tasks_completed: 0,
    jobs_matched: 0,
    reports_generated: 0
  });

  const activeItem = activeTab?.item ?? "";


  const handleLogout = async () => {
    if (!logoutConfirming) {
      setLogoutConfirming(true)

      logoutTimerRef.current = setTimeout(() => {
        setLogoutConfirming(false)
      }, 1500);

      return
    }

    try {
      if (logoutTimerRef.current) clearTimeout(logoutTimerRef.current)
      
      manuallyClosedRef.current = true;
      wsRef.current?.close()

      const token = localStorage.getItem("auth_token")

      const BASE_URL = import.meta.env.VITE_BACKEND_URL || "/api";

      await fetch(`${BASE_URL}/auth/logout`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });
    }
    catch (err) {
      console.error("logout failed:", err);
    } finally {
      logout();
    }
  };
  

  // Mouse tracking for gradient effect
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePosition({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    console.log("ACTIVE TAB:", activeTab);
  }, [activeTab]);
  // WebSocket connection
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const manuallyClosedRef = useRef(false);
  

  useEffect(() => {
    connectWebSocket();
    return () => {
      manuallyClosedRef.current = true;
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);

      wsRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const token = localStorage.getItem("auth_token")
        const BASE_URL = import.meta.env.VITE_BACKEND_URL || "/api";


        const res = await fetch(`${BASE_URL}/stats`, {
          headers: {
            Authorization : `Bearer ${token}`
          }
        })
        const data = await res.json();
  
        setBackendStats({
          tasks_completed: data.tasks_completed ?? 0,
          jobs_matched: data.jobs_matched ?? 0,
          reports_generated: data.reports_generated ?? 0
        });
  
        addLog("📊 Stats loaded from backend", "info");
      } catch (err) {
        console.error("Failed to fetch stats:", err);
      }
    };
  
    fetchStats();
  }, []);
  
  const connectWebSocket = () => {
    try {
      const token =localStorage.getItem("auth_token")
      const protocol = window.location.protocol === "https:" ? "wss" : "ws";
      const WS_URL = `${protocol}://${window.location.host}/api/ws/events`;
      const ws = new WebSocket(`${WS_URL}?token=${token}`)

      let userId = null;
      if (token) {
        try {
          const payload = JSON.parse(atob(token.split('.')[1]));
          userId = payload.user_id;
        } catch (e) {
          console.error("Invalid token");
        }
      }
      
      ws.onopen = () => {
        setWsConnected(true);
        addLog('🔌 Connected to backend event stream', 'success');
        
        pingref.current = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 30000);
      };

      ws.onmessage = (event) => {
        let data;
        try {
          data = JSON.parse(event.data);

          switch (data.event_type){
            case "ui.verification.show":
              setActiveTab({
                group: "Command Center",
                item: "Email Verification"
              });

              setShowLogs(false);
              break;
            
            case "ui.chat.show":
              setShowChat(true);
              setActiveTab({
                group: "Command Center",
                item: "Agent Progress"
              });

              setShowLogs(false);
              break;
          }
        } catch (error) {
          console.error("Failed to parse WebSocket message:", error);
          return;
        }

        if (data.type === "stats_update" && data.user_id === userId) {
          setBackendStats({
            tasks_completed: data.payload.tasks_completed,
            jobs_matched: data.payload.jobs_matched,
            reports_generated: data.payload.reports_generated
          });
        
          addLog("📊 Stats updated", "info");
          return;
        }

        if (data.type === "thinking_agent") {
          setIsThinking(true);
          setCurrentAgent(data.agent);
          setCurrentStage(data.stage);
          setThinkingMessage(data.message);
          return;
        }
      
        if (data.type === "narration_stream") {
          setIsThinking(false);
          setCurrentAgent("");
          setCurrentStage("");
          setThinkingMessage("");
          setChatMessages((prev) => {
            const last = prev[prev.length - 1];
            
          
            if (last && last.agent === data.agent && !last.done) {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  content: last.content + data.content
                }
              ];
            }
      
            return [
              ...prev,
              {
                id: Date.now() + Math.random(),
                type: 'Autonomous_agent',
                role: data.role || 'AI Agent',
                agent: data.agent,
                content: data.content,
                timestamp: new Date(),
                isNew: true,
                done: false
              }
            ];
          });
          return;
        }

        if (data.type === "thinking_done") {
          setIsThinking(false);
          setCurrentAgent("");
          setCurrentStage("");
          setThinkingMessage("");
          return;
        }
       
        if (data.type === "narration_done") {
          setIsThinking(false)

          setChatMessages((prev) => {
            const last = prev[prev.length - 1];
            if (!last) return prev;
      
            return [
              ...prev.slice(0, -1),
              { ...last, done: true }
            ];
          });
          return;
        }
     
      };
      
      ws.onerror = () => {
        setWsConnected(false);
        addLog('WebSocket connection error', 'error');
      };
      
      ws.onclose = () => {
        setWsConnected(false);
        if (pingref.current) {
          clearInterval(pingref.current);
          pingref.current = null;
        }

        addLog('🔌 Disconnected from backend', 'warning');
        
        if (!manuallyClosedRef.current) {
          reconnectTimeoutRef.current = setTimeout(() => {
            addLog('🔄 Attempting to reconnect...', 'info');
            connectWebSocket();
          }, 3000);
        }
      };
      
      wsRef.current = ws;
    } catch (error) {
      setWsConnected(false);
    }
  };

 

  const addLog = useCallback((message: string, type = 'info') => {
    const newLog = {
      id: Date.now() + Math.random(),
      message,
      type,
      timestamp: new Date().toLocaleTimeString()
    };
    setBackendLogs(prev => [...prev, newLog]);
  }, []);

  const stats = [
    { label: 'Tasks Completed', value: backendStats.tasks_completed, icon: CheckCircle },
    { label: 'Jobs Matched', value: backendStats.jobs_matched, icon: Briefcase },
    { label: 'Reports Generated', value: backendStats.reports_generated, icon: FileText }
  ];

  const tabs = [
    { id: 'chat', label: 'Agent Progress', icon: MessageSquare },
    { id: 'jobs', label: 'Job Matching', icon: Briefcase },
    { id: 'verify', label: 'Email Verification', icon: Shield }
  ];

  const sidebarWidth = sidebarExpanded ? 280: 64;

  const commandCenterItems =  ["Agent Progress", "Job Matching", "Email Verification"]
  const topLevelPages = [
    "Overview",
    "Live Activity",
    "System Health",
    "Real-Time Events",
    "Active Operations",
    "Upgrade Plan",
  ]

  const isTopLevelPage = topLevelPages.includes(activeItem);
  const iscommandCenterItems = commandCenterItems.includes(activeItem);

  return (
    <div className="flex min-h-screen w-full overflow-x-hidden bg-background">
  
      {/* Sidebar */}
      <AppSidebar 
      active={activeTab} 
      onSelect={setActiveTab} 
      expanded={sidebarExpanded}
      setExpanded={setsidebarExpanded}
      />
  
      {/* Main Content */}
      <main
        className="flex-1 min-w-0 w-full overflow-x-hidden pl-16 lg:pl-0">
    
        <div className="min-h-screen bg-background relative overflow-hidden">
  
          {/* Animated background gradient */}
          <div
            className="fixed inset-0 pointer-events-none transition-opacity duration-500"
            style={{
              background: `radial-gradient(circle at ${mousePosition.x}px ${mousePosition.y}px, hsl(var(--primary) / 0.08) 0%, transparent 50%)`
            }}
          />
  
          {/* Particle background */}
          <ParticleBackground />
  
          {/* Grid pattern overlay */}
          <div
            className="fixed inset-0 pointer-events-none opacity-[0.02]"
            style={{
              backgroundImage:
                'linear-gradient(hsl(var(--primary)) 1px, transparent 1px), linear-gradient(90deg, hsl(var(--primary)) 1px, transparent 1px)',
              backgroundSize: '50px 50px'
            }}
          />
  
          {/* Header */}
          <motion.header
            transition={{
              type: "spring",
              stiffness: 120,
              damping: 20
            }}

            className="fixed top-0 right-0 left-16 lg:left-[var(--sidebar-width)] z-50 border-b border-border/50"
            style={{
              ["--sidebar-width" as any]: `${sidebarWidth}px`,
              backgroundColor: `hsl(var(--background) / ${headerOpacity})`,
              backdropFilter: `blur(${headerBlur}px)`
            }}
          >
            <div className="max-w-7xl mx-auto px-3 sm:px-6 py-3 sm:py-4">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
  
                {/* LEFT */}
                <motion.div
                  className="flex items-center gap-4 cursor-pointer"
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5 }}
                  onClick={() =>{
                    setActiveTab({
                      group: "Command Center",
                      item: "Agent Progress"
                    });
                    setShowLogs(false)
                  }}
                >
                  <motion.div
                    className="relative"
                    whileHover={{ scale: 1.05 }}
                    whileTap={{ scale: 0.95 }}
                  >
                    <div className="absolute -inset-1 bg-gradient-to-r from-primary to-secondary rounded-xl blur opacity-50" />
  
                    <div className="relative w-12 h-12 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
                      <Brain className="w-7 h-7 text-primary-foreground" />
                    </div>
                  </motion.div>
  
                  <div>
                    <h1 className="text-2xl font-bold gradient-text font-heading">
                      AutoAgent OS
                    </h1>
  
                    <p className="text-xs text-muted-foreground">
                      Autonomous Multi-Agent Intelligence
                    </p>
                  </div>
                </motion.div>
  
                {/* RIGHT */}
                <motion.div
                  className="flex flex-wrap items-center gap-2 sm:gap-4"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.5, delay: 0.1 }}
                >
  
                  {/* Connection status */}
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    className={`flex items-center gap-2 px-4 py-2 rounded-full border transition-all ${
                      wsConnected
                        ? 'bg-accent/10 border-accent/30'
                        : 'bg-destructive/10 border-destructive/30'
                    }`}
                  >
                    <div
                      className={`relative w-2 h-2 rounded-full ${
                        wsConnected ? 'bg-accent' : 'bg-destructive'
                      }`}
                    >
                      {wsConnected && <span className="pulse-ring" />}
                    </div>
  
                    <Zap
                      className={`w-4 h-4 ${
                        wsConnected ? 'text-accent' : 'text-destructive'
                      }`}
                    />
  
                    <span
                      className={`text-xs font-medium ${
                        wsConnected ? 'text-accent' : 'text-destructive'
                      }`}
                    >
                      {wsConnected ? 'Live' : 'Offline'}
                    </span>
                  </motion.div>
  
                  {/* Agent count */}
                  <motion.div
                    whileHover={{ scale: 1.05 }}
                    className="flex items-center gap-2 px-4 py-2 bg-primary/10 border border-primary/30 rounded-full"
                  >
                    <Server className="w-4 h-4 text-primary" />
  
                    <span className="text-xs text-primary font-medium">
                     Multi Agents
                    </span>
                  </motion.div>
  
                  {/* Logout */}
                  <motion.button
                    onClick={handleLogout}
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.97 }}
                    className={`relative px-4 py-2 rounded-full text-xs font-medium flex items-center gap-2 overflow-hidden transition-all duration-250 border ${
                      logoutConfirming
                        ? 'border-red-500/80 text-red-400 bg-red-500/12'
                        : 'border-red-500/30 text-red-500/80 hover:border-red-500/60 hover:text-red-400'
                    }`}
                  >
                    <svg
                      className={`w-3.5 h-3.5 transition-transform duration-250 ${
                        logoutConfirming ? '' : 'group-hover:translate-x-0.5'
                      }`}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
                      <polyline points="16 17 21 12 16 7" />
                      <line x1="21" y1="12" x2="9" y2="12" />
                    </svg>
  
                    {logoutConfirming
                      ? 'Click again to confirm'
                      : 'Sign out'}
  
                    {logoutConfirming && (
                      <motion.div
                        className="absolute bottom-0 left-0 h-[2px] bg-red-500 rounded-full"
                        initial={{ width: 0 }}
                        animate={{ width: '100%' }}
                        transition={{ duration: 2.2, ease: 'linear' }}
                      />
                    )}
                  </motion.button>
  
                </motion.div>
              </div>
            </div>
          </motion.header>

          {/* Hero Section */}
          {!isTopLevelPage && (
          <section className="pt-32 pb-20 px-6">
            <div className="max-w-7xl mx-auto text-center">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.6 }}
                className="mb-8"
              >
                <motion.div 
                  whileHover={{ scale: 1.02 }}
                  className="inline-flex items-center gap-2 px-6 py-3 glass-panel mb-8 cursor-default"
                >
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 4, repeat: Infinity, ease: 'linear' }}
                  >
                    <Sparkles className="w-5 h-5 text-yellow-400" />
                  </motion.div>
                  <span className="text-sm font-semibold text-primary">Powered by Autonomous AI Agents </span>
                </motion.div>
              </motion.div>
              
              <motion.h2 
                initial={{ opacity: 0, y: 30 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.7, delay: 0.1 }}
                className="text-3xl sm:text-5xl md:text-6xl font-bold mb-8 leading-tight flex flex-col items-center gap-3"
              >
                <span className="gradient-text font-heading text-4xl sm:text-6xl md:text-7xl -mt-3 sm:-mt-6">AutoAgent OS</span>
                <span className="text-3xl md:text-3xl text-foreground font-sans font-light tracking-widest text-muted-foreground -mt-3">Autonomous Multi-Agents</span>
                <span className="text-muted-foreground font-light text-2xl md:text-2xl font-sans tracking-tight max-w-2xl mt-7">
                An autonomous AI system that finds, refines, and optimizes your job search until you succeed.
                </span>
              </motion.h2>
              
              {currentRunId && (
                <motion.div 
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="mb-8 inline-flex items-center gap-2 px-4 py-2 bg-secondary/20 border border-secondary/30 rounded-full"
                >
                  <Database className="w-4 h-4 text-secondary" />
                  <span className="text-sm text-secondary font-mono">
                    Run: {currentRunId.slice(0, 12)}...
                  </span>
                </motion.div>
              )}
              
              {/* Stats */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mx-auto mt-16">
                {stats.map((stat, i) => (
                  <StatCard key={i} stat={stat} index={i} />
                ))}
              </div>
            </div>
          </section>
          )}

          {/* Command Center tabs: Agent Progress, Job Matching, Email Verification */}
          {iscommandCenterItems && (
            <section className="pt-24 max-w-7xl mx-auto px-6 pb-20">
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="flex gap-2 mb-8 glass-panel p-2 overflow-x-auto"
              >
                {tabs.map(tab => (
                  <TabButton
                    key={tab.id}
                    tab={tab}
                    isActive={activeTab.item === tab.label}
                    onClick={() => setActiveTab({ group: "Command Center", item: tab.label })}
                  />
                ))}
              </motion.div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <motion.div
                  layout
                  className={showLogs ? "lg:col-span-2" : "lg:col-span-3"}
                  transition={{ duration: 0.4, ease: 'easeInOut' }}
                >
                  <AnimatePresence mode="wait">
                    {activeTab.item === 'Agent Progress' && (
                      <motion.div key="chat" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} transition={{ duration: 0.3 }}>
                        {showChat ? (
                          <RAGChatInterface
                            messages={chatMessages}
                            isProcessing={isChatProcessing}
                            isThinking={isThinking}
                            ThinkingMessage={ThinkingMessage}
                            currentStage={currentStage}
                            currentAgent={currentAgent}
                          />
                        ) : (
                          <PreChatShowcase setActiveTab={setActiveTab} />
                        )}
                      </motion.div>
                    )}
                    {activeTab.item === 'Job Matching' && (
                      <motion.div key="jobs" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} transition={{ duration: 0.3 }}>
                        <JobMatching setTaskId={setTaskId} addLog={addLog} setShowLogs={setShowLogs} />
                      </motion.div>
                    )}
                    {activeTab.item === 'Email Verification' && (
                      <motion.div key="verify" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} transition={{ duration: 0.3 }}>
                        <EmailVerificationSection
                          addLog={addLog}
                          onVerificationSuccess={(newTaskId) => {
                            setTaskId(newTaskId);
                            setShowChat(true);
                            setShowLogs(false);
                            setActiveTab({ group: "Command Center", item: "Agent Progress" });
                          }}
                          setShowLogs={setShowLogs}
                          setReportUrl={setReportUrl}
                          taskID={taskId}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>
                </motion.div>

                <AnimatePresence>
                  {showLogs && (
                    <motion.div
                      initial={{ opacity: 0, x: 50 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: 50 }}
                      transition={{ duration: 0.4, ease: 'easeInOut' }}
                      className="lg:col-span-1"
                    >
                      <BackendLogsPanel
                        logs={backendLogs}
                        reportUrl={reportUrl}
                        wsConnected={wsConnected}
                        currentRunId={currentRunId}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </section>
          )}

          {/* Top-level sidebar pages: Overview, System Health, Live Activity, etc. */}
          {isTopLevelPage && (
            <section className="pt-24 max-w-7xl mx-auto px-6 pb-20">
              <AnimatePresence mode="wait">
                {activeTab.item === "Overview" && (
                  <motion.div key="overview" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <OverviewDashboard />
                  </motion.div>
                )}
                {activeTab.item === "Live Activity" && (
                  <motion.div key="live" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <LiveActivity />
                  </motion.div>
                )}
                {activeTab.item === "System Health" && (
                  <motion.div key="health" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <SystemHealth />
                  </motion.div>
                )}
                {activeTab.item === "Real-Time Events" && (
                  <motion.div key="events" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <RealtimeEvents />
                  </motion.div>
                )}
                {activeTab.item === "Active Operations" && (
                  <motion.div key="ops" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <ActiveOperations />
                  </motion.div>
                )}
                {activeTab.item === "Upgrade Plan" && (
                  <motion.div key="subscription" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                    <SubscriptionPage />
                  </motion.div>
                )}
              </AnimatePresence>
            </section>
          )}

          {/* Any other sidebar item not in either list — coming soon */}
          {!isTopLevelPage && !iscommandCenterItems && (
            <section className="pt-24 max-w-7xl mx-auto px-6 pb-20">
              <div className="glass-panel p-12 text-center">
                <Sparkles className="w-10 h-10 mx-auto mb-4 text-primary opacity-50" />
                <h3 className="text-lg font-semibold text-foreground mb-2">{activeTab.item}</h3>
                <p className="text-sm text-muted-foreground mb-6">This section is coming soon.</p>
                <motion.button
                  whileHover={{ scale: 1.02 }}
                  whileTap={{ scale: 0.98 }}
                  onClick={() => setActiveTab({ group: "Command Center", item: "Agent Progress" })}
                  className="px-5 py-2.5 rounded-xl bg-primary text-primary-foreground text-sm font-semibold"
                >
                  Back to Dashboard
                </motion.button>
              </div>
            </section>
          )}
      </div>
    </main>
   </div>
  );
};

// RAG Chat Interface
const RAGChatInterface = ({
  messages,
  isProcessing,
  isThinking,
  ThinkingMessage,
  currentStage,
  currentAgent,
}: {
  messages: AgentDashboardChatItem[];
  isProcessing: boolean;
  isThinking?: boolean;
  ThinkingMessage?: string;
  currentStage?: string;
  currentAgent?: string | null;
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [newestMessageId, setNewestMessageId] = useState<number | null>(null);
  const firstRenderRef = useRef(true);

  useEffect(() => {

    if (firstRenderRef.current){
      firstRenderRef.current = false;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    if (messages.length > 0) {
      setNewestMessageId(messages[messages.length - 1].id);
    }
  }, [messages, isThinking]);

  return (
    <div className="glass-panel overflow-hidden">
      {/* Header */}
      <div className="p-6 border-b border-border/50 bg-gradient-to-r from-primary/10 to-secondary/10">
        <div className="flex items-center gap-4">
          <motion.div 
            whileHover={{ scale: 1.05, rotate: 5 }}
            className="relative"
          >
            <div className="absolute -inset-1 bg-gradient-to-r from-primary to-secondary rounded-xl blur opacity-50" />
            <div className="relative w-14 h-14 bg-gradient-to-br from-primary to-secondary rounded-xl flex items-center justify-center">
              <MessageSquare className="w-7 h-7 text-primary-foreground" />
            </div>
          </motion.div>
          <div>
            <h3 className="text-xl font-bold text-foreground">AI Career Assistant</h3>
            <p className="text-sm text-muted-foreground">Real-time job matching progress</p>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <div className="w-2 h-2 bg-accent rounded-full animate-pulse" />
            <span className="text-xs text-accent">Active</span>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="h-[500px] overflow-y-auto p-6 space-y-4 bg-gradient-to-b from-background/50 to-card/30">

        <AnimatePresence>
          {messages.map((msg) => (
            <ChatMessage 
              key={msg.id} 
              message={msg} 
              isNew={msg.id === newestMessageId && msg.isNew !== false}
            />
          ))}
        </AnimatePresence>
        
        <AnimatePresence>
          {isProcessing && <ProcessingIndicator />}
        </AnimatePresence>

        {isThinking && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex justify-start"
            >
              <div className="max-w-[90%]">
                <div className="glass-panel p-4 flex items-center gap-3">
                  
                  {/* Animated dots */}
                  <div className="flex gap-1.5">
                    {[0, 1, 2].map((i) => (
                      <motion.div
                        key={i}
                        className="w-2 h-2 bg-primary rounded-full"
                        animate={{ scale: [1, 1.4, 1], opacity: [0.5, 1, 0.5] }}
                        transition={{ duration: 0.8, repeat: Infinity, delay: i * 0.2 }}
                      />
                    ))}
                  </div>

                  {/* Text */}
                  <span className="text-sm text-muted-foreground">
                    {ThinkingMessage?.trim()
                      ? ThinkingMessage
                      : currentStage?.trim()
                        ? currentStage
                        : currentAgent
                          ? `${currentAgent} is analyzing...`
                          : "Thinking..."}
                  </span>
                </div>
              </div>
            </motion.div>
          )}
      
        <div ref={messagesEndRef} />
      </div>

      {/* Footer info */}
      <div className="p-6 border-t border-border/50 bg-card/30">
        <motion.div 
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-panel p-4"
        >
          <div className="flex items-start gap-3">
            <motion.div
              animate={{ rotate: [0, 10, -10, 0] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Rocket className="w-5 h-5 text-primary mt-0.5" />
            </motion.div>
            <div>
              <p className="text-sm font-semibold text-foreground mb-2">How it works:</p>
              <ol className="text-xs text-muted-foreground space-y-1">
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">1</span>
                  Upload your resume in the <strong className="text-foreground">Job Matching</strong> tab
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">2</span>
                  Watch live updates here as our AI agents work
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-primary/20 text-primary text-xs flex items-center justify-center">3</span>
                  Get personalized job recommendations via email
                </li>
              </ol>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  );
};

// Job Matching Component
const JobMatching = ({ setTaskId, addLog, setShowLogs }: any) => {
  const [file, setFile] = useState<File | null>(null);
  const [email, setEmail] = useState('');
  const [keywords, setKeywords] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(e.type === "dragenter" || e.type === "dragover");
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files?.[0]) setFile(e.dataTransfer.files[0]);
  };

  const handleSubmit = async () => {
    if (!file) {
      addLog("Complete Captcha verification first");
      return;
    } 
  

    setIsSubmitting(true);
    setShowLogs(true);
    
    addLog('🚀 Starting job matching process...', 'info');
    addLog(`📄 Processing file: ${file.name}`, 'info');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_email', email);
    formData.append('keywords', keywords);

    try {
      addLog('📤 Uploading resume to backend...', 'info');
      const BASE =  import.meta.env.VITE_BACKEND_URL || "/api";

      const token = localStorage.getItem("auth_token")

      const response = await fetch(`${BASE}/resume/upload`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);

      const data = await response.json();
      localStorage.setItem('pendingUserID', data.task_id);
      
      addLog('✅ Resume uploaded successfully', 'success');
      addLog(`📋 Task ID: ${data.task_id}`, 'info');
      setTaskId(data.task_id);
      
      if (data.verification_required) {
        addLog('🔐 Email verification required', 'warning');
        addLog(`📧 Verification email sent to: ${email || 'extracted email'}`, 'info');
      }
      
      setFile(null);
      setEmail('');
      setKeywords('');
    } catch (error: any) {
      addLog('❌ Error: ' + error.message, 'error');
      addLog('💡 Make sure your backend is running on /api', 'warning');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="glass-panel p-8">
      <div className="flex items-center gap-4 mb-8">
        <motion.div 
          whileHover={{ scale: 1.05, rotate: 5 }}
          className="relative"
        >
          <div className="absolute -inset-1 bg-gradient-to-r from-secondary to-purple-500 rounded-xl blur opacity-50" />
          <div className="relative w-14 h-14 bg-gradient-to-br from-secondary to-purple-500 rounded-xl flex items-center justify-center">
            <Briefcase className="w-7 h-7 text-secondary-foreground" />
          </div>
        </motion.div>
        <div>
          <h3 className="text-2xl font-bold text-foreground">Job Matching Agent</h3>
          <p className="text-muted-foreground">AI-powered career matching</p>
        </div>
      </div>

      <div className="space-y-6">
        {/* File upload */}
        <motion.div
          whileHover={{ scale: 1.01 }}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer ${
            dragActive 
              ? 'border-primary bg-primary/10' 
              : file 
                ? 'border-accent bg-accent/10' 
                : 'border-border hover:border-primary/50 hover:bg-primary/5'
          }`}
        >
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer block">
            <motion.div
              animate={dragActive ? { scale: 1.1 } : { scale: 1 }}
              transition={{ type: 'spring', stiffness: 300 }}
            >
              <Upload className={`w-12 h-12 mx-auto mb-4 ${dragActive ? 'text-primary' : file ? 'text-accent' : 'text-muted-foreground'}`} />
            </motion.div>
            {file ? (
              <motion.div 
                initial={{ scale: 0.9, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                className="flex items-center justify-center gap-2 text-accent"
              >
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">{file.name}</span>
              </motion.div>
            ) : (
              <>
                <p className="text-lg font-semibold text-foreground mb-2">Drop resume or click to browse</p>
                <p className="text-sm text-muted-foreground">PDF, DOCX, TXT (Max 10MB)</p>
              </>
            )}
          </label>
        </motion.div>

        {/* Email input */}
        <div>
          <label className="block text-sm font-semibold text-foreground mb-3">Email (Optional)</label>
          <motion.input
            whileFocus={{ scale: 1.01 }}
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="your.email@example.com"
            className="w-full px-4 py-3 bg-card border-2 border-border rounded-xl focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-foreground placeholder-muted-foreground outline-none"
          />
          <p className="text-xs text-muted-foreground mt-2">If not provided, we'll extract it from your resume</p>
        </div>

        {/* Keywords input */}
        <div>
          <label className="block text-sm font-semibold text-foreground mb-3">Keywords (optional)</label>
          <motion.input
            whileFocus={{ scale: 1.01 }}
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="python, AI, backend"
            className="w-full px-4 py-3 bg-card border-2 border-border rounded-xl focus:border-primary focus:ring-2 focus:ring-primary/20 transition-all text-foreground placeholder-muted-foreground outline-none"
          />
        </div>

        {/* Submit button */}
        <motion.button
          whileHover={{ scale: 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleSubmit}
          disabled={isSubmitting || !file}
          className="w-full relative overflow-hidden bg-gradient-to-r from-primary to-secondary text-primary-foreground py-4 rounded-xl font-semibold disabled:opacity-50 disabled:cursor-not-allowed glow-button"
        >
          <span className="relative z-10 flex items-center justify-center gap-2">
            {isSubmitting ? (
              <>
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                >
                  <Loader className="w-5 h-5" />
                </motion.div>
                Processing...
              </>
            ) : (
              <>
                Find Jobs
                <ArrowRight className="w-5 h-5" />
              </>
            )}
          </span>
        </motion.button>
      </div>
    </div>
  );
};

// Email Verification Component
const EmailVerificationSection = ({ addLog, setShowLogs, setReportUrl, taskID, onVerificationSuccess}: any) => {
  const [code, setCode] = useState(['', '', '', '', '', '']);
  const [loading, setLoading] = useState(false);
  const BASE_URL = import.meta.env.VITE_BACKEND_URL || "/api";
  const [message, setMessage] = useState({ text: '', type: '' });
  const inputRefs = useRef<(HTMLInputElement | null)[]>([]);

  const handleChange = (index: number, value: string) => {
    if (!/^\d*$/.test(value)) return;
    if (value.length > 1) value = value[0];

    const newCode = [...code];
    newCode[index] = value;
    setCode(newCode);

    if (value && index < 5) inputRefs.current[index + 1]?.focus();
  };

  const handlePaste = (e: React.ClipboardEvent) => {
    e.preventDefault();
    const pastedData = e.clipboardData.getData('text').trim();
    const digits = pastedData.replace(/\D/g, '').slice(0, 6);
    if (digits.length > 0) {
      const newCode = [...code];
      for (let i = 0; i < digits.length && i < 6; i++) newCode[i] = digits[i];
      setCode(newCode);
      inputRefs.current[Math.min(digits.length, 5)]?.focus();
      addLog('📋 Verification code pasted', 'info');
    }
  };

  const handleVerify = async () => {
    const fullCode = code.join('');
    if (fullCode.length !== 6) {
      setMessage({ text: 'Please enter the complete 6-digit code', type: 'error' });
      return;
    }

    setLoading(true);
    setMessage({ text: '', type: '' });
    setShowLogs(true);
    addLog('🔐 Starting email verification...', 'info');

    try {
      const token = localStorage.getItem("auth_token")
      const storedtaskID = localStorage.getItem('pendingUserID');
      const response = await fetch(`${BASE_URL}/resume/verify-email`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded',
          Authorization: `Bearer ${token}`,
        },
        body: new URLSearchParams({ task_id: storedtaskID || '', code: fullCode })
      });

      const result = await response.json();
      
      if (result.task_id) {
      localStorage.setItem('pendingUserID', result.task_id);
      }

      if (response.ok && result.success) {
        addLog('✅ Email verified successfully!', 'success');
        setMessage({ text: '✅ Email verified! Job matching will continue automatically.', type: 'success' });
        setCode(['', '', '', '', '', '']);

        if (onVerificationSuccess) {
          onVerificationSuccess(result.task_id || taskID);
        }
      } else {
        const errorMsg = result.error || result.message || 'Invalid code';
        addLog('❌ Verification failed: ' + errorMsg, 'error');
        setMessage({ text: '❌ ' + errorMsg, type: 'error' });
        setCode(['', '', '', '', '', '']);
        inputRefs.current[0]?.focus();
      }
    } catch (error: any) {
      addLog('❌ Network error: ' + error.message, 'error');
      setMessage({ text: '❌ Network error. Please try again.', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="glass-panel p-8">
      <div className="flex items-center gap-4 mb-8">
        <motion.div 
          whileHover={{ scale: 1.05, rotate: 5 }}
          className="relative"
        >
          <div className="absolute -inset-1 bg-gradient-to-r from-accent to-emerald-500 rounded-xl blur opacity-50" />
          <div className="relative w-14 h-14 bg-gradient-to-br from-accent to-emerald-500 rounded-xl flex items-center justify-center">
            <Shield className="w-7 h-7 text-accent-foreground" />
          </div>
        </motion.div>
        <div>
          <h3 className="text-2xl font-bold text-foreground">Email Verification (2FA)</h3>
          <p className="text-muted-foreground">Verify your email to receive reports</p>
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-semibold text-foreground mb-4">6-Digit Verification Code</label>
          <div className="flex justify-between gap-3">
            {code.map((digit, index) => (
              <motion.input
                key={index}
                ref={(el) => (inputRefs.current[index] = el)}
                whileFocus={{ scale: 1.05 }}
                type="text"
                inputMode="numeric"
                maxLength={1}
                value={digit}
                onChange={(e) => handleChange(index, e.target.value)}
                onPaste={index === 0 ? handlePaste : undefined}
                onKeyDown={(e) => {
                  if (e.key === 'Backspace' && !code[index] && index > 0) {
                    inputRefs.current[index - 1]?.focus();
                  }
                }}
                className="w-14 h-16 text-center text-2xl font-bold bg-card border-2 border-border focus:border-accent focus:ring-2 focus:ring-accent/20 rounded-xl text-foreground transition-all outline-none"
              />
            ))}
          </div>
          <p className="text-xs text-muted-foreground mt-3">💡 Tip: You can paste the entire code in the first box</p>
        </div>

        <AnimatePresence>
          {message.text && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className={`p-4 rounded-xl border ${
                message.type === 'success' 
                  ? 'bg-accent/10 border-accent/30 text-accent' 
                  : 'bg-destructive/10 border-destructive/30 text-destructive'
              }`}
            >
              {message.text}
            </motion.div>
          )}
        </AnimatePresence>

        <motion.button
          whileHover={{ scale: 1.02, y: -2 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleVerify}
          disabled={loading}
          className="w-full relative overflow-hidden bg-gradient-to-r from-accent to-emerald-500 text-accent-foreground py-4 rounded-xl font-semibold disabled:opacity-50 glow-button"
        >
          <span className="relative z-10 flex items-center justify-center gap-2">
            {loading ? (
              <>
                <motion.div animate={{ rotate: 360 }} transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}>
                  <Loader className="w-5 h-5" />
                </motion.div>
                Verifying...
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5" />
                Verify Email
              </>
            )}
          </span>
        </motion.button>

        <motion.div 
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="glass-panel p-4"
        >
          <p className="text-sm font-semibold text-foreground mb-3">How it works:</p>
          <ol className="text-sm text-muted-foreground space-y-2">
            {['Upload your resume in the Job Matching tab', 'Check your email for the 6-digit code', 'Enter the code here', 'Watch real-time logs as agents process your request!'].map((step, i) => (
              <li key={i} className="flex items-center gap-3">
                <span className="w-6 h-6 rounded-full bg-primary/20 text-primary text-xs font-bold flex items-center justify-center shrink-0">
                  {i + 1}
                </span>
                {step}
              </li>
            ))}
          </ol>
        </motion.div>
      </div>
    </div>
  );
};

// Backend Logs Panel
const BackendLogsPanel = ({ logs, reportUrl, wsConnected, currentRunId }: any) => {
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getLogColor = (type: string) => {
    switch (type) {
      case 'error': return 'bg-destructive/20 text-destructive border-l-destructive';
      case 'warning': return 'bg-yellow-500/20 text-yellow-400 border-l-yellow-500';
      case 'success': return 'bg-accent/20 text-accent border-l-accent';
      default: return 'bg-primary/20 text-primary border-l-primary';
    }
  };

  return (
    <div className="glass-panel overflow-hidden h-[700px] flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-border/50 bg-card/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Terminal className="w-5 h-5 text-accent" />
            <h3 className="font-bold text-foreground">Backend Logs</h3>
          </div>
          <motion.div 
            animate={wsConnected ? { scale: [1, 1.2, 1] } : {}}
            transition={{ duration: 2, repeat: Infinity }}
            className="flex items-center gap-2"
          >
            <Activity className={`w-4 h-4 ${wsConnected ? 'text-accent' : 'text-destructive'}`} />
            <span className={`text-xs font-medium ${wsConnected ? 'text-accent' : 'text-destructive'}`}>
              {wsConnected ? 'Live' : 'Offline'}
            </span>
          </motion.div>
        </div>

        {currentRunId && (
          <motion.div 
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-3 p-2 bg-secondary/10 border border-secondary/20 rounded-lg"
          >
            <div className="flex items-center gap-2">
              <Database className="w-3 h-3 text-secondary" />
              <span className="text-xs text-secondary font-mono truncate">{currentRunId}</span>
            </div>
          </motion.div>
        )}
    </div>

      {/* Logs */}
      <div className="flex-1 overflow-y-auto p-4 space-y-2 font-mono text-sm">
        <AnimatePresence>
          {logs.length === 0 ? (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="text-center text-muted-foreground py-8"
            >
              <Network className="w-8 h-8 mx-auto mb-3 opacity-50" />
              {wsConnected ? 'Waiting for events...' : 'Reconnecting...'}
            </motion.div>
          ) : (
            logs.map((log: any) => (
              <motion.div
                key={log.id}
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                className={`p-2 rounded-lg border-l-2 ${getLogColor(log.type)}`}
              >
                <span className="text-muted-foreground opacity-60">[{log.timestamp}]</span> {log.message}
              </motion.div>
            ))
          )}
        </AnimatePresence>
        <div ref={logsEndRef} />
      </div>

      {/* Report Download */}
      <AnimatePresence>
        {reportUrl && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 20 }}
            className="p-4 border-t border-border/50 bg-gradient-to-r from-accent/10 to-emerald-500/10"
          >
            <div className="flex items-center gap-3 mb-3">
              <motion.div
                animate={{ scale: [1, 1.1, 1] }}
                transition={{ duration: 1.5, repeat: Infinity }}
              >
                <CheckCircle className="w-6 h-6 text-accent" />
              </motion.div>
              <div>
                <p className="text-sm font-semibold text-accent">Report Ready!</p>
                <p className="text-xs text-muted-foreground">Your job matching report is ready</p>
              </div>
            </div>
            <motion.a
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              href={reportUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full bg-gradient-to-r from-accent to-emerald-500 text-accent-foreground py-2 px-4 rounded-lg font-semibold flex items-center justify-center gap-2 glow-button"
            >
              <Download className="w-4 h-4" />
              Download Report
            </motion.a>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AgentDashboard;
