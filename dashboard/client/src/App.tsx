import { useEffect, useState, type ElementType, type FormEvent, type ReactNode } from "react";
import { Toaster, toast } from "sonner";
import {
  Activity, AlertTriangle, Archive, ArrowDownToLine, ArrowUpFromLine,
  BarChart3, Bell, BookOpen, CalendarDays, ChevronRight, CircleHelp,
  Clock3, Database, FileText, Fingerprint, Gauge, LayoutDashboard,
  LockKeyhole, LogOut, Menu, Radio, Search, Server, Settings2, ShieldCheck, Users,
  Wifi, X, Zap
} from "lucide-react";
import { Link, Route, Switch, useLocation } from "wouter";
import "./index.css";

type View = "command" | "students" | "attendance" | "history" | "analytics" | "control" | "events" | "demo";
type SystemStatus = { checkin: boolean; checkout: boolean; database: string; hardware: string; api: string; lastEvent?: string };
type Attendance = { id: string; student_id: string; student_name: string; event_type: string; timestamp: string; status: string; method?: string; verification?: Record<string, boolean> };

const nav: { key: View; label: string; icon: ElementType; description: string }[] = [
  { key: "command", label: "Command Center", icon: LayoutDashboard, description: "Live operational overview" },
  { key: "students", label: "Students", icon: Users, description: "Profiles and registration" },
  { key: "attendance", label: "Live Attendance", icon: Radio, description: "Real-time arrivals and exits" },
  { key: "history", label: "Attendance History", icon: CalendarDays, description: "Searchable audit trail" },
  { key: "analytics", label: "Analytics", icon: BarChart3, description: "Trends and performance" },
  { key: "control", label: "System Control", icon: Settings2, description: "Modes and infrastructure" },
  { key: "events", label: "System Events", icon: FileText, description: "Operational audit log" },
  { key: "demo", label: "Demo & Simulation", icon: Zap, description: "Mock hardware operations" },
];

const apiBase = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token = sessionStorage.getItem("child_safety_token");
  const headers: Record<string, string> = { "Content-Type": "application/json", ...(init?.headers as any || {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${apiBase}${path}`, { headers, ...init });
  if (!res.ok) {
    if (res.status === 401 || res.status === 403) {
      sessionStorage.removeItem("child_safety_session");
      sessionStorage.removeItem("child_safety_token");
      window.dispatchEvent(new Event("unauthorized"));
    }
    throw new Error((await res.json().catch(() => null))?.detail || `Request failed (${res.status})`);
  }
  const body = await res.json();
  return body.data ?? body;
}

function App() {
  const [location] = useLocation();
  const [authenticated, setAuthenticated] = useState(() => sessionStorage.getItem("child_safety_session") === "active");
  const [collapsed, setCollapsed] = useState(false);
  const [status, setStatus] = useState<SystemStatus>({ checkin: false, checkout: false, database: "unknown", hardware: "unknown", api: "online" });
  const [events, setEvents] = useState<Attendance[]>([]);
  const [students, setStudents] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>({});
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(new Date());
  const currentView = (location.replace("/", "") || "command") as View;

  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const handleAuth = () => setAuthenticated(false);
    window.addEventListener("unauthorized", handleAuth);
    return () => window.removeEventListener("unauthorized", handleAuth);
  }, []);
  useEffect(() => {
    Promise.allSettled([api<SystemStatus>("/api/system/status"), api<any>("/api/attendance/today"), api<any>("/api/students"), api<any>("/api/dashboard/summary")]).then(([s, a, st, sum]) => {
      if (s.status === "fulfilled") setStatus(s.value);
      if (a.status === "fulfilled") setEvents(a.value.records || []);
      if (st.status === "fulfilled") setStudents(st.value.records || []);
      if (sum.status === "fulfilled") setSummary(sum.value);
      setLoading(false);
    });
  }, []);
  useEffect(() => {
    let socket: WebSocket | undefined;
    try {
      const protocol = location.startsWith("https") ? "wss" : "ws";
      const host = apiBase ? new URL(apiBase).host : window.location.host;
      socket = new WebSocket(`${protocol}://${host}/ws/events`);
      socket.onopen = () => setStatus((s) => ({ ...s, api: "live" }));
      socket.onmessage = (message) => {
        const payload = JSON.parse(message.data);
        if (payload.event === "attendance" && payload.data) setEvents((current) => [payload.data, ...current].slice(0, 8));
        if (payload.event === "system_status") setStatus((current) => ({ ...current, ...payload.data }));
      };
    } catch { /* backend may be unavailable during first-run */ }
    return () => socket?.close();
  }, []);

  const navigate = (key: View) => { window.history.pushState({}, "", key === "command" ? "/" : `/${key}`); window.dispatchEvent(new PopStateEvent("popstate")); };
  const toggleMode = async (mode: "checkin" | "checkout") => {
    const next = !status[mode];
    try {
      const data = await api<SystemStatus>(`/api/system/${mode}/${next ? "start" : "stop"}`, { method: "POST" });
      setStatus(data); toast.success(`${mode === "checkin" ? "Check-in" : "Check-out"} mode ${next ? "started" : "stopped"}`);
    } catch (error) { toast.error(error instanceof Error ? error.message : "Unable to reach backend"); }
  };

  if (!authenticated) return <Login onSuccess={() => { sessionStorage.setItem("child_safety_session", "active"); setAuthenticated(true); }} />;
  return <div className="min-h-screen bg-[#07100f] text-[#dbe9e5] selection:bg-emerald-300/20">
    <Toaster theme="dark" position="bottom-right" />
    <aside className={`${collapsed ? "w-[76px]" : "w-[264px]"} fixed inset-y-0 left-0 z-30 hidden border-r border-white/[0.07] bg-[#091512]/95 backdrop-blur-xl transition-all lg:flex lg:flex-col`}>
      <div className="flex h-[84px] items-center gap-3 border-b border-white/[0.07] px-5">
        <div className="brand-mark"><ShieldCheck size={21} strokeWidth={2.2} /></div>
        {!collapsed && <div><div className="text-[11px] font-semibold tracking-[0.22em] text-emerald-200/80">AI CHILD SAFETY</div><div className="mt-0.5 text-[13px] font-medium tracking-[0.1em] text-white">CONTROL CENTER</div></div>}
      </div>
      <div className="flex-1 px-3 py-5">
        {!collapsed && <div className="eyebrow mb-3 px-3">Operations</div>}
        <nav className="space-y-1">{nav.map(({ key, label, icon: Icon, description }) => <button key={key} onClick={() => navigate(key)} title={collapsed ? `${label} — ${description}` : undefined} className={`nav-item ${currentView === key ? "nav-active" : ""} ${collapsed ? "justify-center px-0" : ""}`}><Icon size={17} /><span className={collapsed ? "hidden" : ""}>{label}</span>{!collapsed && currentView === key && <ChevronRight className="ml-auto text-emerald-300" size={15} />}</button>)}</nav>
        {!collapsed && <div className="mt-8 px-3"><div className="eyebrow mb-3">System integrity</div><div className="mini-status"><span className="status-dot status-green" /> API channel <span className="ml-auto text-emerald-300">{status.api === "live" ? "LIVE" : "READY"}</span></div><div className="mini-status"><span className={`status-dot ${status.database === "connected" ? "status-green" : "status-amber"}`} /> Database <span className="ml-auto text-slate-400">{status.database.toUpperCase()}</span></div></div>}
      </div>
      <div className="border-t border-white/[0.07] p-3"><button onClick={() => setCollapsed(!collapsed)} className="nav-item w-full justify-center text-slate-500 hover:text-white"><Menu size={17} /><span className={collapsed ? "hidden" : ""}>Collapse menu</span></button><div className={`mt-2 flex items-center gap-3 rounded-xl border border-white/[0.07] bg-white/[0.025] p-3 ${collapsed ? "justify-center" : ""}`}><div className="avatar">AD</div>{!collapsed && <div className="min-w-0"><div className="truncate text-xs font-semibold text-white">Admin Desk</div><div className="truncate text-[10px] text-slate-500">Authorized operator</div></div>}</div></div>
    </aside>
    <main className={`${collapsed ? "lg:pl-[76px]" : "lg:pl-[264px]"} min-h-screen transition-all`}>
      <header className="sticky top-0 z-20 flex h-[84px] items-center justify-between border-b border-white/[0.07] bg-[#07100f]/85 px-5 backdrop-blur-xl sm:px-8"><div className="flex items-center gap-4"><button onClick={() => setCollapsed(!collapsed)} className="icon-button lg:hidden"><Menu size={19} /></button><div><div className="eyebrow">{nav.find((x) => x.key === currentView)?.description || "Live operational overview"}</div><h1 className="mt-1 text-xl font-semibold tracking-tight text-white sm:text-2xl">{nav.find((x) => x.key === currentView)?.label || "Command Center"}</h1></div></div><div className="flex items-center gap-3"><div className="hidden text-right sm:block"><div className="text-[11px] font-medium text-slate-400">{now.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" })}</div><div className="mono mt-0.5 text-sm text-white">{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</div></div><div className="live-chip"><span className="status-dot status-green pulse" />{status.api === "live" ? "REAL-TIME" : "API READY"}</div><button className="icon-button relative"><Bell size={17} /><span className="notification-dot" /></button><button onClick={() => { sessionStorage.removeItem("child_safety_session"); setAuthenticated(false); }} className="icon-button"><LogOut size={17} /></button></div></header>
      <div className="px-5 py-6 sm:px-8 sm:py-8"><Switch><Route path="/" component={() => <CommandCenter status={status} events={events} students={students} loading={loading} onToggle={toggleMode} onNavigate={navigate} />} /><Route path="/students" component={() => <Students students={students} />} /><Route path="/attendance" component={() => <Attendance events={events} />} /><Route path="/history" component={() => <Attendance events={events} historical />} /><Route path="/analytics" component={() => <Analytics summary={summary} />} /><Route path="/control" component={() => <Control status={status} onToggle={toggleMode} />} /><Route path="/events" component={() => <Events events={events} />} /><Route path="/demo" component={() => <DemoSimulation />} /></Switch></div>
    </main>
  </div>;
}

function Login({ onSuccess }: { onSuccess: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true);
    try { const res: any = await api("/api/auth/login", { method: "POST", body: JSON.stringify({ username, password }) }); sessionStorage.setItem("child_safety_token", res.token); onSuccess(); }
    catch (error) { toast.error(error instanceof Error ? error.message : "Unable to sign in"); }
    finally { setBusy(false); }
  };
  return <div className="login-shell"><div className="login-grid" /><div className="login-card"><div className="brand-mark"><ShieldCheck size={21} strokeWidth={2.2} /></div><div className="eyebrow mt-7 text-emerald-300/80">Protected operator access</div><h1 className="mt-3 text-3xl font-semibold tracking-tight text-white">Welcome back.</h1><p className="mt-3 text-sm leading-6 text-slate-500">Sign in to the AI Child Safety System command center. Access is verified by the backend.</p><form onSubmit={submit} className="mt-7 space-y-4"><label className="login-label">Username or email<input required autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} placeholder="operator@organization" /></label><label className="login-label">Password<input required type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Enter your password" /></label><button disabled={busy} className="button-primary mt-2 w-full justify-center">{busy ? "VERIFYING ACCESS..." : "SIGN IN SECURELY"}<LockKeyhole size={15} /></button></form><div className="mt-7 flex items-center gap-2 border-t border-white/[0.07] pt-5 text-[10px] uppercase tracking-[0.13em] text-slate-600"><span className="status-dot status-green" /> Backend-authenticated session <span className="ml-auto">TLS / API</span></div></div><div className="login-footer"><ShieldCheck size={15} /> Child safety operations <span>•</span> Authorized personnel only</div></div>;
}

function SectionTitle({ eyebrow, title, action }: { eyebrow: string; title: string; action?: ReactNode }) { return <div className="mb-5 flex items-end justify-between"><div><div className="eyebrow">{eyebrow}</div><h2 className="mt-1 text-lg font-semibold text-white">{title}</h2></div>{action}</div>; }
function Metric({ label, value, icon: Icon, accent = "green", detail }: { label: string; value: string | number; icon: ElementType; accent?: string; detail: string }) { return <div className="metric-card"><div className={`metric-icon ${accent}`}><Icon size={17} /></div><div className="mt-5 text-2xl font-semibold tracking-tight text-white">{value}</div><div className="mt-1 text-xs font-medium text-slate-400">{label}</div><div className="mt-4 border-t border-white/[0.06] pt-3 text-[10px] uppercase tracking-[0.15em] text-slate-600">{detail}</div></div>; }
function StatusPill({ active, label }: { active: boolean; label: string }) { return <span className={`status-pill ${active ? "active" : "unknown"}`}><span className="status-dot" />{label}</span>; }
function CommandCenter({ status, events, students, loading, onToggle, onNavigate }: { status: SystemStatus; events: Attendance[]; students: any[]; loading: boolean; onToggle: (mode: "checkin" | "checkout") => void; onNavigate: (v: View) => void }) {
  const present = new Set(events.filter((e) => e.event_type === "check-in").map((e) => e.student_id)).size; const inside = Math.max(0, present - new Set(events.filter((e) => e.event_type === "check-out").map((e) => e.student_id)).size);
  return <div className="mx-auto max-w-[1500px] animate-enter"><div className="hero-panel mb-6"><div className="relative z-10 max-w-xl"><div className="eyebrow text-emerald-300/80">Operational overview / {new Date().toLocaleDateString()}</div><h2 className="mt-3 text-3xl font-semibold tracking-[-0.03em] text-white sm:text-4xl">Security, attendance<br /><span className="text-emerald-300">and trust in one view.</span></h2><p className="mt-4 max-w-md text-sm leading-6 text-slate-400">The live command layer for your child safety network. Monitor arrivals, coordinate modes, and keep every handoff auditable.</p><div className="mt-6 flex flex-wrap gap-3"><button onClick={() => onNavigate("attendance")} className="button-primary"><Radio size={15} /> Open live feed</button><button onClick={() => onNavigate("control")} className="button-quiet"><Settings2 size={15} /> System controls</button></div></div><div className="hero-orbit"><div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" /><div className="orbit-core"><Fingerprint size={28} /><span>SECURE<br />CHANNEL</span></div><div className="orbit-spark spark-a" /><div className="orbit-spark spark-b" /></div></div>
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Metric label="Registered students" value={loading ? "—" : students.length} icon={Users} detail="MongoDB students" /><Metric label="Present today" value={loading ? "—" : present} icon={ShieldCheck} accent="teal" detail="Verified check-ins" /><Metric label="Currently inside" value={loading ? "—" : inside} icon={Activity} accent="amber" detail="Open attendance" /><Metric label="System events" value={events.length} icon={Zap} accent="blue" detail="Live session" /></div>
    <div className="mt-7 grid gap-6 xl:grid-cols-[1.25fr_.75fr]"><div className="panel"><SectionTitle eyebrow="Control layer" title="Modes & system status" action={<button onClick={() => onNavigate("control")} className="text-xs font-medium text-emerald-300 hover:text-emerald-200">Full controls <ChevronRight className="inline" size={14} /></button>} /><div className="grid gap-3 sm:grid-cols-2"><ModeCard label="Check-in mode" active={status.checkin} icon={ArrowDownToLine} onToggle={() => onToggle("checkin")} /><ModeCard label="Check-out mode" active={status.checkout} icon={ArrowUpFromLine} onToggle={() => onToggle("checkout")} /></div><div className="mt-5 grid grid-cols-2 gap-3 border-t border-white/[0.06] pt-5 sm:grid-cols-4"><div className="inline-stat"><Database size={15} /><span>Database</span><b className={status.database === "connected" ? "text-emerald-300" : "text-amber-300"}>{status.database.toUpperCase()}</b></div><div className="inline-stat"><Server size={15} /><span>API service</span><b className="text-emerald-300">{status.api.toUpperCase()}</b></div><div className="inline-stat"><Wifi size={15} /><span>Hardware</span><b className="text-amber-300">{status.hardware.toUpperCase()}</b></div><div className="inline-stat"><Clock3 size={15} /><span>Last event</span><b>{status.lastEvent ? new Date(status.lastEvent).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}</b></div></div></div><LiveFeed events={events} onNavigate={onNavigate} /></div>
    <div className="mt-6 grid gap-6 lg:grid-cols-[1.1fr_.9fr]"><div className="panel"><SectionTitle eyebrow="Telemetry" title="Attendance pulse" action={<button onClick={() => onNavigate("analytics")} className="text-xs font-medium text-emerald-300">View analytics <ChevronRight className="inline" size={14} /></button>} /><div className="chart-grid"><div className="chart-y"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><div className="bars">{[0, 0, 0, 0, 0, 0, 0].map((height, i) => <div key={i} className="bar-col"><div className={`bar-value ${height === 0 ? "empty-bar" : ""}`} style={{ height: `${height}%` }} /><span>{["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][i]}</span></div>)}</div></div><div className="mt-5 flex gap-5 text-[10px] uppercase tracking-[0.14em] text-slate-500"><span><i className="legend-dot bg-emerald-300" />Verified attendance</span><span><i className="legend-dot bg-slate-700" />No telemetry</span></div></div><div className="panel"><SectionTitle eyebrow="Infrastructure" title="Signal health" /><div className="space-y-4"><HealthRow label="Backend API" value={status.api === "live" ? "Operational" : "Ready for connection"} percent={status.api === "live" ? 100 : 76} icon={Server} /><HealthRow label="MongoDB Atlas" value={status.database === "connected" ? "Connected" : "Awaiting connection"} percent={status.database === "connected" ? 100 : 30} icon={Database} warn={status.database !== "connected"} /><HealthRow label="Hardware layer" value="Telemetry unknown" percent={0} icon={Radio} warn /></div><div className="mt-5 border-t border-white/[0.06] pt-4 text-xs leading-5 text-slate-500"><AlertTriangle className="mr-1 inline text-amber-300" size={13} /> Physical hardware status is never inferred by the dashboard.</div></div></div>
  </div>;
}
function ModeCard({ label, active, icon: Icon, onToggle }: { label: string; active: boolean; icon: ElementType; onToggle: () => void }) { return <div className={`mode-card ${active ? "mode-active" : ""}`}><div className="flex items-start justify-between"><div className={`mode-icon ${active ? "bg-emerald-300/15 text-emerald-300" : "bg-white/[0.04] text-slate-500"}`}><Icon size={18} /></div><StatusPill active={active} label={active ? "ACTIVE" : "STOPPED"} /></div><div className="mt-5 text-sm font-semibold text-white">{label}</div><button onClick={onToggle} className={`mt-4 w-full rounded-lg border py-2 text-xs font-semibold tracking-wide transition ${active ? "border-rose-400/20 bg-rose-400/[0.05] text-rose-300 hover:bg-rose-400/10" : "border-emerald-300/20 bg-emerald-300/[0.06] text-emerald-300 hover:bg-emerald-300/10"}`}>{active ? "STOP MODE" : "START MODE"}</button></div>; }
function LiveFeed({ events, onNavigate }: { events: Attendance[]; onNavigate: (v: View) => void }) { return <div className="panel"><SectionTitle eyebrow="WebSocket stream" title="Live attendance feed" action={<button onClick={() => onNavigate("attendance")} className="text-xs font-medium text-emerald-300">Open feed <ChevronRight className="inline" size={14} /></button>} />{events.length === 0 ? <Empty title="No attendance events today" body="Verified RFID and face events will appear here automatically." /> : <div className="space-y-1">{events.slice(0, 5).map((event) => <div key={event.id || `${event.student_id}-${event.timestamp}`} className="event-row"><div className={`event-icon ${event.event_type === "check-out" ? "checkout" : "checkin"}`}>{event.event_type === "check-out" ? <ArrowUpFromLine size={14} /> : <ArrowDownToLine size={14} />}</div><div className="min-w-0 flex-1"><div className="truncate text-sm font-medium text-slate-200">{event.student_name || "Unknown student"}</div><div className="mt-0.5 text-[11px] text-slate-500">{event.event_type} · {event.method || "verified"}</div></div><div className="mono text-[11px] text-slate-500">{new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div></div>)}</div>}</div>; }
function HealthRow({ label, value, percent, icon: Icon, warn }: { label: string; value: string; percent: number; icon: ElementType; warn?: boolean }) { return <div><div className="mb-2 flex items-center gap-2 text-xs"><Icon size={14} className={warn ? "text-amber-300" : "text-emerald-300"} /><span className="font-medium text-slate-300">{label}</span><span className={`ml-auto ${warn ? "text-amber-300" : "text-slate-500"}`}>{value}</span></div><div className="meter"><span className={warn ? "meter-warn" : "meter-good"} style={{ width: `${percent}%` }} /></div></div>; }
function Empty({ title, body }: { title: string; body: string }) { return <div className="empty-state"><CircleHelp size={22} /><div className="mt-3 text-sm font-medium text-slate-300">{title}</div><div className="mt-1 max-w-xs text-center text-xs leading-5 text-slate-600">{body}</div></div>; }
function Students({ students }: { students: any[] }) { const [query, setQuery] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ student_id: "", name: "", guardian_name: "", guardian_relationship: "guardian", guardian_phone: "" });
  const [saving, setSaving] = useState(false);
  const [faceImage, setFaceImage] = useState<File | null>(null);
  const filtered = students.filter((s) => `${s.name} ${s.student_id} ${s.guardian_name}`.toLowerCase().includes(query.toLowerCase()));
  const register = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true);
    try { const body = new FormData(); body.append('payload', JSON.stringify(form)); if (faceImage) body.append('face_image', faceImage); const response = await fetch(`${apiBase}/api/students/register-with-face`, { method: 'POST', body }); if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'Registration failed'); toast.success('Student registered successfully'); setShowForm(false); setFaceImage(null); setForm({ student_id: "", name: "", guardian_name: "", guardian_relationship: "guardian", guardian_phone: "" }); }
    catch (error) { toast.error(error instanceof Error ? error.message : 'Unable to register student'); }
    finally { setSaving(false); }
  };
  return <div className="mx-auto max-w-[1500px] animate-enter"><SectionTitle eyebrow="Directory / protected records" title="Students" action={<button onClick={() => setShowForm(true)} className="button-primary"><Users size={15} /> Register student</button>} /><div className="panel"><div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center"><div className="search-box"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search by name, ID, guardian..." /></div><div className="ml-auto flex gap-2"><button className="filter-button">All statuses <ChevronRight size={13} /></button><button className="filter-button">Export <ArrowDownToLine size={13} /></button></div></div>{filtered.length === 0 ? <Empty title={students.length === 0 ? "No students registered yet" : "No matching students"} body="Student profiles returned by the backend will appear in this protected directory." /> : <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Student</th><th>Student ID</th><th>Guardian</th><th>Status</th><th>Registered</th></tr></thead><tbody>{filtered.map((s) => <tr key={s.student_id}><td><div className="flex items-center gap-3"><div className="avatar small">{(s.name || "??").slice(0, 2).toUpperCase()}</div><span className="font-medium text-white">{s.name}</span></div></td><td className="mono text-slate-400">{s.student_id}</td><td className="text-slate-400">{s.guardian_name || "—"}</td><td><span className="table-status">{(s.status || "active").toUpperCase()}</span></td><td className="text-slate-500">{s.created_at ? new Date(s.created_at).toLocaleDateString() : "—"}</td></tr>)}</tbody></table></div>}</div>{showForm && <div className="modal-backdrop"><form onSubmit={register} className="modal-card"><div className="flex items-start justify-between"><div><div className="eyebrow">Protected enrollment</div><h3 className="mt-2 text-lg font-semibold text-white">Register student</h3></div><button type="button" className="icon-button" onClick={() => setShowForm(false)}><X size={16} /></button></div><div className="mt-6 grid gap-4 sm:grid-cols-2"><label className="login-label">Student ID<input required value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} placeholder="STU-001" /></label><label className="login-label">Full name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Student name" /></label><label className="login-label">Guardian name<input required value={form.guardian_name} onChange={(e) => setForm({ ...form, guardian_name: e.target.value })} placeholder="Guardian name" /></label><label className="login-label">Guardian phone<input required value={form.guardian_phone} onChange={(e) => setForm({ ...form, guardian_phone: e.target.value })} placeholder="+91 ..." /></label><label className="login-label sm:col-span-2">Face image (optional)<input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => setFaceImage(e.target.files?.[0] || null)} /></label></div><div className="mt-6 flex justify-end gap-2"><button type="button" className="button-quiet" onClick={() => setShowForm(false)}>Cancel</button><button disabled={saving} className="button-primary">{saving ? 'REGISTERING...' : 'REGISTER STUDENT'}</button></div></form></div>}</div>; }
function Attendance({ events, historical = false }: { events: Attendance[]; historical?: boolean }) { const [query, setQuery] = useState(""); const filtered = events.filter((e) => `${e.student_name} ${e.student_id}`.toLowerCase().includes(query.toLowerCase())); return <div className="mx-auto max-w-[1500px] animate-enter"><SectionTitle eyebrow={historical ? "Audit trail / date ranges" : "WebSocket stream / today"} title={historical ? "Attendance History" : "Live Attendance"} /><div className="panel"><div className="mb-5 flex flex-col gap-3 sm:flex-row"><div className="search-box"><Search size={15} /><input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search attendance records..." /></div><button className="filter-button">{historical ? "This month" : "Today"} <CalendarDays size={13} /></button><button className="filter-button">All statuses <ChevronRight size={13} /></button></div>{filtered.length === 0 ? <Empty title={historical ? "No attendance records found" : "No live attendance events"} body="The API will populate this table as the face, RFID, and guardian verification pipeline records events." /> : <div className="overflow-x-auto"><table className="data-table"><thead><tr><th>Student</th><th>Student ID</th><th>Event</th><th>Timestamp</th><th>Method</th><th>Verification</th></tr></thead><tbody>{filtered.map((e) => <tr key={e.id || e.timestamp}><td className="font-medium text-white">{e.student_name}</td><td className="mono text-slate-400">{e.student_id}</td><td><span className={`event-label ${e.event_type === "check-out" ? "out" : "in"}`}>{e.event_type}</span></td><td className="mono text-slate-400">{new Date(e.timestamp).toLocaleString()}</td><td className="text-slate-400">{e.method || "—"}</td><td className="text-emerald-300">Verified</td></tr>)}</tbody></table></div>}</div></div>; }
function Analytics({ summary }: { summary: any }) { return <div className="mx-auto max-w-[1500px] animate-enter"><SectionTitle eyebrow="Decision support / MongoDB aggregations" title="Analytics" /><div className="grid gap-6 lg:grid-cols-[1.35fr_.65fr]"><div className="panel"><SectionTitle eyebrow="Attendance rate" title="Daily trend" /><div className="chart-grid tall"><div className="chart-y"><span>100%</span><span>75%</span><span>50%</span><span>25%</span><span>0%</span></div><div className="bars">{[0, 0, 0, 0, 0, 0, 0].map((height, i) => <div key={i} className="bar-col"><div className="bar-value empty-bar" style={{ height: `${height}%` }} /><span>{["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][i]}</span></div>)}</div></div><Empty title="Awaiting attendance telemetry" body="Charts become meaningful once the backend returns aggregated records." /></div><div className="panel"><SectionTitle eyebrow="Operational readout" title="Key indicators" /><div className="space-y-3"><div className="readout"><span>Check-ins today</span><b>{summary?.checkins_today ?? "—"}</b></div><div className="readout"><span>Currently Present</span><b>{summary?.currently_present ?? "—"}</b></div><div className="readout"><span>Total Students</span><b>{summary?.total_students ?? "—"}</b></div><div className="readout"><span>Failed Verifications</span><b>{summary?.failed_verifications ?? "—"}</b></div></div><div className="mt-6 rounded-lg border border-amber-300/10 bg-amber-300/[0.04] p-3 text-xs leading-5 text-slate-500"><AlertTriangle className="mr-1 inline text-amber-300" size={13} /> Showing live backend data.</div></div></div></div>; }
function Control({ status, onToggle }: { status: SystemStatus; onToggle: (mode: "checkin" | "checkout") => void }) { return <div className="mx-auto max-w-[1100px] animate-enter"><SectionTitle eyebrow="Authorized operations" title="System Control" /><div className="grid gap-6 md:grid-cols-2"><div className="panel"><div className="eyebrow">Attendance modes</div><h3 className="mt-2 text-lg font-semibold text-white">Command controls</h3><p className="mt-2 text-sm leading-6 text-slate-500">Every mode change is validated and recorded by the backend. Contradictory modes are rejected server-side.</p><div className="mt-6 space-y-3"><ModeCard label="Check-in mode" active={status.checkin} icon={ArrowDownToLine} onToggle={() => onToggle("checkin")} /><ModeCard label="Check-out mode" active={status.checkout} icon={ArrowUpFromLine} onToggle={() => onToggle("checkout")} /></div></div><div className="panel"><div className="eyebrow">Infrastructure state</div><h3 className="mt-2 text-lg font-semibold text-white">Trust boundary</h3><div className="mt-6 space-y-4"><HealthRow label="FastAPI service" value={status.api.toUpperCase()} percent={status.api === "live" ? 100 : 70} icon={Server} /><HealthRow label="MongoDB Atlas" value={status.database.toUpperCase()} percent={status.database === "connected" ? 100 : 30} icon={Database} warn={status.database !== "connected"} /><HealthRow label="RFID / camera / Pi" value="UNKNOWN" percent={0} icon={Radio} warn /></div></div></div></div>; }
function Events({ events }: { events: Attendance[] }) { return <div className="mx-auto max-w-[1500px] animate-enter"><SectionTitle eyebrow="Auditability / immutable intent" title="System Events" /><div className="panel">{events.length === 0 ? <Empty title="No system events found" body="Administrative actions and verification events will be recorded by the backend." /> : <div className="space-y-1">{events.map((e) => <div className="event-row" key={e.id || e.timestamp}><div className="event-icon checkin"><Zap size={14} /></div><div className="flex-1"><div className="text-sm font-medium text-slate-200">{e.event_type} · {e.student_name}</div><div className="mt-1 text-xs text-slate-500">{e.method || "system event"}</div></div><div className="mono text-xs text-slate-500">{new Date(e.timestamp).toLocaleString()}</div></div>)}</div>}</div></div>; }

export default App;

function DemoSimulation() {
  const [studentId, setStudentId] = useState("");
  const simulate = async (endpoint: string, method: string = "POST") => {
    try {
      await api(`/api/system/${endpoint}`, { method });
      toast.success(`Simulated ${endpoint} successfully`);
    } catch (err: any) {
      toast.error(err.message || "Simulation failed");
    }
  };
  return <div className="mx-auto max-w-[1100px] animate-enter">
    <SectionTitle eyebrow="HARDWARE_MODE=mock" title="Demo & Simulation" />
    <div className="grid gap-6 md:grid-cols-2">
      <div className="panel">
        <div className="eyebrow">Input Simulation</div>
        <h3 className="mt-2 text-lg font-semibold text-white">Student Events</h3>
        <label className="login-label mt-4">Target Student ID
          <input value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="STU-..." />
        </label>
        <div className="mt-4 flex flex-col gap-2">
          <button onClick={() => simulate(`mock/rfid/${studentId || 'UNKNOWN'}`)} className="button-primary w-full justify-center">Simulate RFID Scan</button>
          <button onClick={() => simulate(`mock/face/${studentId || 'UNKNOWN'}`)} className="button-primary w-full justify-center">Simulate Face Recognition</button>
          <button onClick={() => simulate(`mock/guardian/${studentId || 'UNKNOWN'}?success=true`)} className="button-quiet w-full justify-center">Simulate Guardian Success</button>
          <button onClick={() => simulate(`mock/guardian/${studentId || 'UNKNOWN'}?success=false`)} className="button-quiet w-full justify-center text-rose-300">Simulate Guardian Failure</button>
        </div>
      </div>
    </div>
  </div>;
}
