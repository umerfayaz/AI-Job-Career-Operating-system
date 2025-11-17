import React, { useState, useEffect } from 'react';
import { Upload, FileText, Briefcase, Mail, CheckCircle, AlertCircle, Loader, Search, TrendingUp, Zap, ArrowRight, Brain, Eye, Target, Activity, Users, Cpu } from 'lucide-react';

const AgentDashboard = () => {
  const [activeTab, setActiveTab] = useState('research');
  const [taskId, setTaskId] = useState('');
  const [status, setStatus] = useState('idle');
  const [scrollY, setScrollY] = useState(0);
  const [animatedStats, setAnimatedStats] = useState({ tasks: 0, jobs: 0, reports: 0 });
  const [liveAgents, setLiveAgents] = useState([]);

  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  useEffect(() => {
    const targets = { tasks: 1247, jobs: 3892, reports: 856 };
    const duration = 2000;
    const steps = 60;
    const interval = duration / steps;
    let current = { tasks: 0, jobs: 0, reports: 0 };
    
    const timer = setInterval(() => {
      current = {
        tasks: Math.min(current.tasks + Math.ceil(targets.tasks / steps), targets.tasks),
        jobs: Math.min(current.jobs + Math.ceil(targets.jobs / steps), targets.jobs),
        reports: Math.min(current.reports + Math.ceil(targets.reports / steps), targets.reports)
      };
      setAnimatedStats(current);
      if (current.tasks >= targets.tasks) clearInterval(timer);
    }, interval);
    
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <header className={`fixed w-full z-50 transition-all duration-300 ${scrollY > 50 ? 'bg-white/90 backdrop-blur-xl shadow-lg' : 'bg-white/70 backdrop-blur-md'}`}>
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-xl flex items-center justify-center transform hover:rotate-12 transition-transform">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                Agentic AI System
              </h1>
              <p className="text-xs text-slate-500">Multi-Agent Platform</p>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="hidden md:flex items-center gap-2 px-4 py-2 bg-green-50 rounded-full">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              <span className="text-sm font-medium text-green-700">6 Agents Active</span>
            </div>
          </div>
        </div>
      </header>

      <section className="pt-32 pb-20 px-6 relative">
        <div className="absolute top-20 left-10 w-72 h-72 bg-blue-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob pointer-events-none" />
        <div className="absolute top-40 right-10 w-72 h-72 bg-indigo-200 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-blob animation-delay-2000 pointer-events-none" />
        
        <div className="max-w-7xl mx-auto relative z-10">
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-100 rounded-full mb-6">
              <Zap className="w-4 h-4 text-blue-600" />
              <span className="text-sm font-medium text-blue-700">Powered by LangGraph AI</span>
            </div>
            
            <h2 className="text-5xl md:text-6xl font-bold mb-6 bg-gradient-to-r from-slate-900 via-blue-900 to-indigo-900 bg-clip-text text-transparent leading-tight">
              Autonomous AI Research
              <br />
              & Career Assistant
            </h2>
            
            <p className="text-xl text-slate-600 max-w-2xl mx-auto mb-8">
              Multi-agent system for intelligent research and job matching
            </p>
            
            <div className="grid grid-cols-3 gap-8 max-w-3xl mx-auto mt-12">
              {[
                { label: 'Tasks Completed', value: animatedStats.tasks, icon: CheckCircle, color: 'blue' },
                { label: 'Jobs Matched', value: animatedStats.jobs, icon: Briefcase, color: 'indigo' },
                { label: 'Reports Generated', value: animatedStats.reports, icon: FileText, color: 'purple' }
              ].map((stat, i) => (
                <div key={i} className="bg-white rounded-2xl p-6 shadow-lg hover:shadow-xl transform hover:-translate-y-1 transition-all">
                  <stat.icon className={`w-8 h-8 text-${stat.color}-600 mx-auto mb-2`} />
                  <div className="text-3xl font-bold text-slate-900">{stat.value.toLocaleString()}</div>
                  <div className="text-sm text-slate-600">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="max-w-6xl mx-auto px-6 pb-20 relative z-20">
        <div className="flex gap-4 mb-8 bg-white rounded-2xl p-2 shadow-lg">
          {[
            { id: 'research', label: 'Research Agent', icon: Search },
            { id: 'jobs', label: 'Job Matching', icon: Briefcase }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex-1 flex items-center justify-center gap-2 px-6 py-4 rounded-xl font-medium transition-all ${
                activeTab === tab.id
                  ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white shadow-lg'
                  : 'text-slate-600 hover:bg-slate-50'
              }`}
            >
              <tab.icon className="w-5 h-5" />
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'research' && <ResearchAgent setTaskId={setTaskId} setStatus={setStatus} setLiveAgents={setLiveAgents} />}
        {activeTab === 'jobs' && <JobMatching setTaskId={setTaskId} setStatus={setStatus} setLiveAgents={setLiveAgents} />}
        {taskId && <StatusDisplay taskId={taskId} status={status} liveAgents={liveAgents} />}
      </section>

      <section className="max-w-7xl mx-auto px-6 py-20 relative z-10">
        <h3 className="text-3xl font-bold text-center mb-12 text-slate-900">
          How Our AI Agents Work
        </h3>
        
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { icon: Brain, title: 'Autonomous Planning', desc: 'AI breaks down tasks into steps', color: 'from-blue-500 to-cyan-500' },
            { icon: Eye, title: 'Multi-Source Research', desc: 'Searches web and databases', color: 'from-indigo-500 to-purple-500' },
            { icon: Target, title: 'Smart Matching', desc: 'Embeddings-based job matching', color: 'from-violet-500 to-pink-500' }
          ].map((feature, i) => (
            <div key={i} className="group bg-white rounded-2xl p-8 shadow-lg hover:shadow-2xl transform hover:-translate-y-2 transition-all">
              <div className={`w-16 h-16 bg-gradient-to-br ${feature.color} rounded-2xl flex items-center justify-center mb-6 group-hover:rotate-12 transition-transform`}>
                <feature.icon className="w-8 h-8 text-white" />
              </div>
              <h4 className="text-xl font-bold mb-3 text-slate-900">{feature.title}</h4>
              <p className="text-slate-600">{feature.desc}</p>
            </div>
          ))}
        </div>
      </section>

      <style>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          33% { transform: translate(30px, -50px) scale(1.1); }
          66% { transform: translate(-20px, 20px) scale(0.9); }
        }
        .animate-blob { animation: blob 7s infinite; }
        .animation-delay-2000 { animation-delay: 2s; }
      `}</style>
    </div>
  );
};

const ResearchAgent = ({ setTaskId, setStatus, setLiveAgents }) => {
  const [task, setTask] = useState('');
  const [taskType, setTaskType] = useState('research');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!task) return;
    
    setIsSubmitting(true);
    setStatus('submitting');
    
    setLiveAgents([
      { name: 'Planner', status: 'active', progress: 0 },
      { name: 'Memory', status: 'waiting', progress: 0 },
      { name: 'Researcher', status: 'waiting', progress: 0 },
      { name: 'Analyzer', status: 'waiting', progress: 0 },
      { name: 'Reasoner', status: 'waiting', progress: 0 },
      { name: 'Generator', status: 'waiting', progress: 0 }
    ]);

    try {
      const response = await fetch('http://localhost:8000/task', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: task,
          task_id: `research_${Date.now()}`,
          priority: 5,
          config: { task_type: taskType }
        })
      });

      const data = await response.json();
      setTaskId(data.task_id);
      setStatus('processing');
      
      simulateAgentProgress(setLiveAgents);
      
      setTask('');
      setEmail('');
    } catch (error) {
      setStatus('error');
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 relative z-30">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-cyan-500 rounded-xl flex items-center justify-center">
          <Search className="w-6 h-6 text-white" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-slate-900">Research Agent</h3>
          <p className="text-slate-600">AI-powered research workflow</p>
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            What would you like to research?
          </label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            placeholder="e.g., Analyze AI trends in healthcare industry"
            className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-blue-500 focus:ring-2 focus:ring-blue-200 transition-all resize-none relative z-30"
            rows={4}
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Research Type</label>
          <select
            value={taskType}
            onChange={(e) => setTaskType(e.target.value)}
            className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-blue-500 transition-all relative z-30"
          >
            <option value="research">General Research</option>
            <option value="analysis">Deep Analysis</option>
            <option value="market">Market Research</option>
            <option value="technical">Technical Research</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">Email (optional)</label>
          <div className="relative z-30">
            <Mail className="absolute left-4 top-3.5 w-5 h-5 text-slate-400 pointer-events-none" />
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              className="w-full pl-12 pr-4 py-3 border-2 border-slate-200 rounded-xl focus:border-blue-500 transition-all"
            />
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={isSubmitting || !task}
          className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 text-white py-4 rounded-xl font-medium hover:shadow-lg transform hover:-translate-y-0.5 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 relative z-30"
        >
          {isSubmitting ? (
            <>
              <Loader className="w-5 h-5 animate-spin" />
              Launching Agents...
            </>
          ) : (
            <>
              Start Research
              <ArrowRight className="w-5 h-5" />
            </>
          )}
        </button>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {['Web Search', 'Deep Analysis', 'Memory Recall', 'Auto-Report'].map((feature, i) => (
          <span key={i} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm font-medium">
            ✓ {feature}
          </span>
        ))}
      </div>
    </div>
  );
};

const JobMatching = ({ setTaskId, setStatus, setLiveAgents }) => {
  const [file, setFile] = useState(null);
  const [keywords, setKeywords] = useState('');
  const [location, setLocation] = useState('Remote');
  const [experienceLevel, setExperienceLevel] = useState('mid');
  const [email, setEmail] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;

    setIsSubmitting(true);
    setStatus('submitting');
    
    setLiveAgents([
      { name: 'Job Planner', status: 'active', progress: 0 },
      { name: 'Job Scraper', status: 'waiting', progress: 0 },
      { name: 'Job Matcher', status: 'waiting', progress: 0 },
      { name: 'Quality Checker', status: 'waiting', progress: 0 },
      { name: 'Report Generator', status: 'waiting', progress: 0 }
    ]);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('user_email', email);
    formData.append('keywords', keywords);
    formData.append('location', location);
    formData.append('experience_level', experienceLevel);

    try {
      const response = await fetch('http://localhost:8000/resume/upload', {
        method: 'POST',
        body: formData
      });

      const data = await response.json();
      setTaskId(data.task_id);
      setStatus('processing');
      
      simulateJobAgentProgress(setLiveAgents);
      
      setFile(null);
      setKeywords('');
      setEmail('');
    } catch (error) {
      setStatus('error');
      console.error(error);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-xl p-8 relative z-30">
      <div className="flex items-center gap-3 mb-6">
        <div className="w-12 h-12 bg-gradient-to-br from-indigo-500 to-purple-500 rounded-xl flex items-center justify-center">
          <Briefcase className="w-6 h-6 text-white" />
        </div>
        <div>
          <h3 className="text-2xl font-bold text-slate-900">Job Matching Agent</h3>
          <p className="text-slate-600">AI-powered career matching</p>
        </div>
      </div>

      <div className="space-y-6">
        <div
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`border-3 border-dashed rounded-xl p-8 text-center transition-all relative z-30 ${
            dragActive ? 'border-indigo-500 bg-indigo-50' : 'border-slate-300 hover:border-slate-400'
          }`}
        >
          <input
            type="file"
            accept=".pdf,.docx,.txt"
            onChange={(e) => setFile(e.target.files[0])}
            className="hidden"
            id="file-upload"
          />
          <label htmlFor="file-upload" className="cursor-pointer">
            <Upload className="w-12 h-12 text-slate-400 mx-auto mb-4" />
            {file ? (
              <div className="flex items-center justify-center gap-2 text-green-600">
                <CheckCircle className="w-5 h-5" />
                <span className="font-medium">{file.name}</span>
              </div>
            ) : (
              <>
                <p className="text-lg font-medium text-slate-700 mb-2">Drop resume or click to browse</p>
                <p className="text-sm text-slate-500">PDF, DOCX, TXT (Max 10MB)</p>
              </>
            )}
          </label>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Keywords</label>
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="python, AI, backend"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 transition-all relative z-30"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Location</label>
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 transition-all relative z-30"
            />
          </div>
        </div>

        <div className="grid md:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Experience</label>
            <select
              value={experienceLevel}
              onChange={(e) => setExperienceLevel(e.target.value)}
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 transition-all relative z-30"
            >
              <option value="entry">Entry Level</option>
              <option value="mid">Mid Level</option>
              <option value="senior">Senior</option>
              <option value="lead">Lead</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="your.email@example.com"
              className="w-full px-4 py-3 border-2 border-slate-200 rounded-xl focus:border-indigo-500 transition-all relative z-30"
              required
            />
          </div>
        </div>

        <button
          onClick={handleSubmit}
          disabled={isSubmitting || !file}
          className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 text-white py-4 rounded-xl font-medium hover:shadow-lg transform hover:-translate-y-0.5 transition-all disabled:opacity-50 flex items-center justify-center gap-2 relative z-30"
        >
          {isSubmitting ? (
            <>
              <Loader className="w-5 h-5 animate-spin" />
              Matching Jobs...
            </>
          ) : (
            <>
              Find Jobs
              <TrendingUp className="w-5 h-5" />
            </>
          )}
        </button>
      </div>

      <div className="mt-6 flex flex-wrap gap-2">
        {['Smart Matching', 'Real-time Scraping', 'Quality Checks', 'PDF Report'].map((f, i) => (
          <span key={i} className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-sm font-medium">
            ✓ {f}
          </span>
        ))}
      </div>
    </div>
  );
};

const StatusDisplay = ({ taskId, status, liveAgents }) => {
  const statusConfig = {
    submitting: { icon: Loader, text: 'Submitting...', color: 'blue', spin: true },
    processing: { icon: Activity, text: 'AI Agents Working...', color: 'indigo', spin: false },
    completed: { icon: CheckCircle, text: 'Completed!', color: 'green', spin: false },
    error: { icon: AlertCircle, text: 'Error', color: 'red', spin: false }
  };

  const config = statusConfig[status] || statusConfig.processing;
  const Icon = config.icon;

  return (
    <div className="mt-8 bg-white rounded-2xl p-6 shadow-xl border-2 border-indigo-100 relative z-30">
      <div className="flex items-center gap-4 mb-6">
        <Icon className={`w-8 h-8 text-${config.color}-600 ${config.spin ? 'animate-spin' : ''}`} />
        <div className="flex-1">
          <h4 className="font-bold text-slate-900 text-lg">{config.text}</h4>
          <p className="text-sm text-slate-600">Task ID: {taskId}</p>
        </div>
      </div>
      
      {status === 'processing' && liveAgents.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center gap-2 mb-4">
            <Users className="w-5 h-5 text-indigo-600" />
            <h5 className="font-semibold text-slate-900">Live Agent Status</h5>
          </div>
          
          {liveAgents.map((agent, i) => (
            <div key={i} className="bg-slate-50 rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <Cpu className={`w-5 h-5 ${agent.status === 'active' ? 'text-green-500 animate-pulse' : agent.status === 'completed' ? 'text-blue-500' : 'text-slate-400'}`} />
                  <span className="font-medium text-slate-900">{agent.name}</span>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full ${
                  agent.status === 'active' ? 'bg-green-100 text-green-700' :
                  agent.status === 'completed' ? 'bg-blue-100 text-blue-700' :
                  'bg-slate-200 text-slate-600'
                }`}>
                  {agent.status}
                </span>
              </div>
              
              {agent.status !== 'waiting' && (
                <div className="w-full bg-slate-200 rounded-full h-2 mt-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-500 ${
                      agent.status === 'completed' ? 'bg-blue-500' : 'bg-green-500'
                    }`}
                    style={{ width: `${agent.progress}%` }}
                  />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const simulateAgentProgress = (setLiveAgents) => {
  const agents = ['Planner', 'Memory', 'Researcher', 'Analyzer', 'Reasoner', 'Generator'];
  let currentIndex = 0;
  
  const interval = setInterval(() => {
    if (currentIndex >= agents.length) {
      clearInterval(interval);
      return;
    }
    
    setLiveAgents(prev => prev.map((agent, i) => {
      if (i === currentIndex) {
        return { ...agent, status: 'active', progress: 50 };
      }
      if (i < currentIndex) {
        return { ...agent, status: 'completed', progress: 100 };
      }
      return agent;
    }));
    
    setTimeout(() => {
      setLiveAgents(prev => prev.map((agent, i) => 
        i === currentIndex ? { ...agent, status: 'completed', progress: 100 } : agent
      ));
      currentIndex++;
    }, 2000);
  }, 3000);
};

const simulateJobAgentProgress = (setLiveAgents) => {
  const agents = ['Job Planner', 'Job Scraper', 'Job Matcher', 'Quality Checker', 'Report Generator'];
  let currentIndex = 0;
  
  const interval = setInterval(() => {
    if (currentIndex >= agents.length) {
      clearInterval(interval);
      return;
    }
    
    setLiveAgents(prev => prev.map((agent, i) => {
      if (i === currentIndex) {
        return { ...agent, status: 'active', progress: 50 };
      }
      if (i < currentIndex) {
        return { ...agent, status: 'completed', progress: 100 };
      }
      return agent;
    }));
    
    setTimeout(() => {
      setLiveAgents(prev => prev.map((agent, i) => 
        i === currentIndex ? { ...agent, status: 'completed', progress: 100 } : agent
      ));
      currentIndex++;
    }, 2500);
  }, 3500);
};

export default AgentDashboard;