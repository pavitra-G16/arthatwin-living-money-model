"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  Sparkles, ShieldAlert, TrendingUp, Brain, Sliders, MessageSquare,
  FileText, Upload, CheckCircle2, AlertTriangle, RefreshCw, Lock, Printer, Send
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from "recharts";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL || "https://arthatwin-living-money-model.onrender.com/api").replace(/\/$/, "");
const API = process.env.NEXT_PUBLIC_API_URL || "https://arthatwin-living-money-model.onrender.com/api";
const PUBLIC_DEMO = process.env.NEXT_PUBLIC_ARTHATWIN_PUBLIC_DEMO === "1";

const CATEGORIES = [
  "Dining Out", "Groceries", "Transport", "Travel", "Subscriptions",
  "Utilities", "Housing", "Health", "Shopping", "Education", "Cash Withdrawal",
  "Transfers", "Transfers / People", "Income", "Refund", "Uncategorised", "Review Required"
];
const SUBSCRIPTION_OPTIONS = ["yes", "no", "unsure"] as const;
const PROFILE_FIELDS: Array<{ label: string; key: keyof Profile }> = [
  { label: "Monthly income", key: "monthly_income" },
  { label: "Fixed monthly costs", key: "fixed_costs" },
  { label: "Emergency fund saved", key: "emergency_fund_current" },
  { label: "Emergency fund target", key: "emergency_fund_target" },
  { label: "Discretionary budget", key: "discretionary_budget" },
];

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6", "#f43f5e"];

type Tab = "overview" | "ledger" | "simulator" | "coach" | "report" | "settings";
type Profile = {
  monthly_income: number;
  fixed_costs: number;
  emergency_fund_current: number;
  emergency_fund_target: number;
  discretionary_budget: number;
};
type Goal = { id: number; name: string; target_amount: number; saved_amount: number; target_date: string; priority: number };
type GoalDraft = Omit<Goal, "id"> & { id?: number };
type Transaction = { id: number; date: string; raw_narration: string; merchant: string; amount: number; txn_type: string; category: string; source: string; confidence_source: string; user_locked: boolean; security_flag: string | null };
type LearnedRule = { id: number; pattern: string; category: string; explanation: string; hit_count: number; is_enabled: boolean; matching_count: number };
type RecurringAlert = { merchant: string; type: string; reason: string; monthly_amount: number; annual_cost: number; still_uses: "yes" | "no" | "unsure" };
type Dashboard = {
  month: string; profile: Profile; goals: Goal[]; transactions: Transaction[];
  learned_rules: LearnedRule[]; recurring_alerts: RecurringAlert[];
  nudges: Array<{ severity: string; title: string; message: string }>;
  category_breakdown: Array<{ name: string; value: number }>;
  total_spent: number; summary: Record<string, number | boolean | null>; data_quality_warnings: string[]; disclaimer: string;
};
type Simulation = {
  simulated_monthly_surplus: number; monthly_delta: number; assumptions: string; subscription_savings?: number;
  goal_impacts: Array<{ goal_name: string; projected_completion: string | null; new_months: number | null; days_saved: number | null }>;
};
type AgentTrace = { event?: string; summary?: string; pattern_extracted?: string; transition?: string; retroactive_updates?: number; tool_selected?: string | null; reason?: string; verified_result?: unknown; ai_enabled?: boolean };
type ChatMessage = { role: "assistant" | "user"; text: string; guardrail?: boolean };
type ImportRow = { row_number: number; date: string | null; merchant: string; raw_narration: string; amount: string; txn_type: string; suggested_category: string; duplicate: boolean; security_flag?: string | null };
type ImportPreview = { preview_id: string; source: string; filename?: string; parsed_count: number; ignored_count: number; rejected_count: number; duplicate_count: number; transactions: ImportRow[]; issues: Array<{ row?: number; message: string }> };
type MonthlyReport = { month: string; income: number; observed_savings: number | null; profile_income_assumption: number; expenses: number; refunds: number; modeled_surplus: number; category_breakdown: Array<{ name: string; value: number }>; recurring_payments: RecurringAlert[]; spending_changes: Array<{ title: string; message: string }>; goals: Array<{ name: string; target_amount: number; saved_amount: number; target_date: string }>; data_quality: { warnings: string[]; [key: string]: unknown }; disclaimer: string };

const formatINR = (value: unknown) => {
  const amount = Number(value ?? 0);
  return (Number.isFinite(amount) ? amount : 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
};

export default function ArthaTwinDashboard() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [activeTab, setActiveTab] = useState<Tab>("overview");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [selectedMonth, setSelectedMonth] = useState("");
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [acceptedRows, setAcceptedRows] = useState<number[]>([]);
  const [dateOverrides, setDateOverrides] = useState<Record<number, string>>({});
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [allowExternalAi, setAllowExternalAi] = useState(false);
  const [coverageConfirmed, setCoverageConfirmed] = useState(false);
  const [agentTrace, setAgentTrace] = useState<AgentTrace | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [profileDraft, setProfileDraft] = useState<Profile | null>(null);
  const [goalDraft, setGoalDraft] = useState<GoalDraft | null>(null);

  // Ingestion states
  const [smsText, setSmsText] = useState("");
  const [ingestBanner, setIngestBanner] = useState("");

  // Simulator states
  const [diningCut, setDiningCut] = useState(30);
  const [rentChange, setRentChange] = useState(0);
  const [cancelSubs, setCancelSubs] = useState(true);
  const [extraIncome, setExtraIncome] = useState(0);
  const [simResult, setSimResult] = useState<Simulation | null>(null);

  // Coach states
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      text: "Namaste! I am ArthaTwin, your Living Money Model coach. Load your bank statements or click 'Load Sample Indian Bank Data' above, then ask me about spending trade-offs or goal timelines."
    }
  ]);

  const fetchDashboard = useCallback(async () => {
    try {
      const res = await fetch(`${API}/dashboard${selectedMonth ? `?month=${selectedMonth}` : ""}`);
      if (!res.ok) throw new Error(`Dashboard request failed (${res.status})`);
      const json = await res.json() as Dashboard;
      setData(json);
      setSelectedMonth(json.month);
      setCoverageConfirmed(Boolean(json.summary.statement_complete_confirmed));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Backend not reachable");
    }
  }, [selectedMonth]);

  const runSimulation = useCallback(async (dCut: number, rChg: number, cSubs: boolean, eInc: number) => {
    try {
      const res = await fetch(`${API}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dining_cut_pct: dCut,
          rent_change: rChg,
          cancel_unused_subs: cSubs,
          extra_income: eInc,
          month: selectedMonth || undefined
        })
      });
      setSimResult(await res.json() as Simulation);
    } catch (e) {
      console.error(e);
    }
  }, [selectedMonth]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void fetchDashboard();
      void runSimulation(30, 0, true, 0);
    }, 0);
    return () => window.clearTimeout(timer);
  }, [fetchDashboard, runSimulation]);

  const handleSeedDemo = async () => {
    setLoading(true);
    const response = await fetch(`${API}/seed-demo`, { method: "POST" });
    if (!response.ok) { const body = await response.json(); setError(body.detail || "Could not load demo data"); setLoading(false); return; }
    const result = await response.json();
    await fetchDashboard();
    await runSimulation(diningCut, rentChange, cancelSubs, extraIncome);
    setIngestBanner(`Synthetic demo loaded: ${result.transactions_loaded} transactions. ${result.message}`);
    setLoading(false);
  };

  const openProfileEditor = () => {
    if (!data) return;
    setProfileDraft({ ...data.profile });
    setGoalDraft(data.goals[0] ? { ...data.goals[0] } : { name: "New goal", target_amount: 100000, saved_amount: 0, target_date: "2027-12-31", priority: 1 });
    setProfileOpen(true);
  };

  const saveProfileAndGoal = async () => {
    if (!profileDraft || !goalDraft?.name.trim() || !goalDraft.target_date || goalDraft.target_amount < goalDraft.saved_amount) { setError("Enter a goal name and date, and ensure the target is at least the amount already saved."); return; }
    const profileResponse = await fetch(`${API}/profile`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(profileDraft) });
    if (!profileResponse.ok) { setError("Profile could not be saved."); return; }
    const goalResponse = await fetch(`${API}/goals`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(goalDraft) });
    if (!goalResponse.ok) { setError("Goal could not be saved."); return; }
    setProfileOpen(false);
    await fetchDashboard();
    await runSimulation(diningCut, rentChange, cancelSubs, extraIncome);
  };

  const handleCategoryFix = async (txnId: number, newCategory: string) => {
    const matching = await fetch(`${API}/transactions/${txnId}/matches?category=${encodeURIComponent(newCategory)}`);
    if (!matching.ok) { setError("Could not preview matching transactions."); return; }
    const matchInfo = await matching.json();
    if (!window.confirm(`Apply “${newCategory}” to ${matchInfo.matching_count} unlocked transactions from ${matchInfo.merchant}? The selected transaction will be locked to your correction.`)) { await fetchDashboard(); return; }
    const res = await fetch(`${API}/transactions/${txnId}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_category: newCategory })
    });
    const json = await res.json() as { agent_trace?: AgentTrace };
    if (json.agent_trace) {
      setAgentTrace(json.agent_trace);
    }
    await fetchDashboard();
    await runSimulation(diningCut, rentChange, cancelSubs, extraIncome);
  };

  const handleSubFeedback = async (merchant: string, still_uses: RecurringAlert["still_uses"]) => {
    await fetch(`${API}/subscriptions/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchant, still_uses })
    });
    await fetchDashboard();
  };

  const handleSmsSubmit = async () => {
    if (!smsText.trim()) return;
    const res = await fetch(`${API}/ingest/sms/preview`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sms_text: smsText })
    });
    await receivePreview(res);
    setSmsText("");
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const formData = new FormData();
    formData.append("file", e.target.files[0]);
    const res = await fetch(`${API}/ingest/file/preview`, { method: "POST", body: formData });
    await receivePreview(res);
    e.target.value = "";
  };

  const receivePreview = async (res: Response) => {
    const body = await res.json();
    if (!res.ok) { setError(body.detail || "Import preview failed"); return; }
    const result = body as ImportPreview;
    setPreview(result);
    setAcceptedRows(result.transactions.filter((row) => !row.duplicate).map((row) => row.row_number));
    setDateOverrides({});
    setError("");
  };

  const confirmImport = async () => {
    if (!preview) return;
    const res = await fetch(`${API}/ingest/confirm`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ preview_id: preview.preview_id, accepted_rows: acceptedRows, date_overrides: dateOverrides }) });
    const body = await res.json();
    if (!res.ok) { setError(body.detail || "Import could not be confirmed"); return; }
    setIngestBanner(`Import complete: ${body.imported} saved, ${body.duplicates} duplicates skipped, ${body.rejected} need review.`);
    setPreview(null);
    await fetchDashboard();
    await runSimulation(diningCut, rentChange, cancelSubs, extraIncome);
  };

  const handleSendChat = async (customPrompt?: string) => {
    const query = customPrompt || chatInput;
    if (!query.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setChatInput("");
    const res = await fetch(`${API}/coach`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: query, month: selectedMonth || undefined, allow_external_ai: allowExternalAi })
    });
    const json = await res.json() as { reply: string; guardrail_triggered: boolean; agent_trace?: AgentTrace };
    if (json.agent_trace) setAgentTrace(json.agent_trace);
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: json.reply, guardrail: json.guardrail_triggered }
    ]);
  };

  useEffect(() => {
    if (!selectedMonth) return;
    void fetch(`${API}/reports/monthly?month=${selectedMonth}`).then((res) => res.ok ? res.json() : null).then((value) => setReport(value));
  }, [selectedMonth, data]);

  const setCoverage = async (confirmed: boolean) => {
    const res = await fetch(`${API}/months/${selectedMonth}/coverage`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ confirmed_complete: confirmed }) });
    const body = await res.json();
    if (!res.ok) setError(body.detail || "Could not save statement coverage");
    else { setCoverageConfirmed(confirmed); await fetchDashboard(); }
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center space-y-3">
          {error ? <AlertTriangle className="w-8 h-8 mx-auto text-amber-400" /> : <RefreshCw className="w-8 h-8 animate-spin mx-auto text-indigo-400" />}
          <p className="text-slate-300">{error ? `Could not load ArthaTwin: ${error}` : "Connecting to ArthaTwin Living Money Engine…"}</p>
          {error && <button onClick={() => { setError(""); void fetchDashboard(); }} className="px-4 py-2 rounded bg-indigo-600">Retry connection</button>}
          <p className="text-xs text-slate-500">Check that the backend is running and NEXT_PUBLIC_API_URL points to its /api endpoint.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans">
      {/* Top Navbar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">
              A
            </div>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white flex items-center gap-2">
                ArthaTwin
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  Living Money Model
                </span>
              </h1>
              <p className="text-xs text-slate-400">Deterministic Financial Twin + Neuro-Symbolic Rule Memory</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {PUBLIC_DEMO && <span className="px-2 py-1 rounded bg-amber-400/15 text-amber-200 border border-amber-400/30 text-xs">Synthetic demo data</span>}
            {!PUBLIC_DEMO && <button
              onClick={handleSeedDemo}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/25 transition cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? "Loading..." : "Load Sample Indian Bank Data"}
            </button>}
          </div>
        </div>

        {/* Navigation Tabs */}
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto border-t border-slate-800/60">
          {[
            { id: "overview", label: "Living Overview", icon: TrendingUp },
            { id: "ledger", label: `Transactions & AI Brain (${data.learned_rules.length} Rules)`, icon: Brain },
            { id: "simulator", label: "What-If Goal Planner", icon: Sliders },
            { id: "coach", label: "Guardrailed Coach", icon: MessageSquare },
            { id: "report", label: "Monthly Review Report", icon: FileText },
            { id: "settings", label: "Privacy & Data", icon: ShieldAlert },
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as Tab)}
                className={`px-4 py-2.5 text-sm font-medium flex items-center gap-2 border-b-2 transition whitespace-nowrap cursor-pointer ${
                  activeTab === tab.id
                    ? "border-indigo-500 text-indigo-300"
                    : "border-transparent text-slate-400 hover:text-slate-200"
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-6">
        {error && <div role="alert" className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-sm text-rose-200">{error}<button onClick={() => setError("")} className="float-right" aria-label="Dismiss error">✕</button></div>}
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-slate-900 border border-slate-800 p-3">
          <label className="text-xs text-slate-400">Reporting month <input aria-label="Reporting month" type="month" value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)} className="ml-2 rounded bg-slate-950 border border-slate-700 px-2 py-1 text-sm text-white" /></label>
          <span className="text-xs text-slate-400">{data.summary.transactions_count ?? data.transactions.length} transactions in selected period</span>
        </div>
        {/* Live Agent Trace Banner */}
        {agentTrace && (
          <div className="p-3.5 rounded-xl bg-indigo-950/70 border border-indigo-500/40 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <Brain className="w-5 h-5 text-indigo-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                  {agentTrace.tool_selected ? `Verified tool • ${agentTrace.tool_selected}` : `Workflow • ${agentTrace.event ?? "Completed"}`}{agentTrace.ai_enabled ? " · optional AI enabled" : ""}
                </div>
                {agentTrace.reason && <p className="text-xs text-slate-400 mt-1">{agentTrace.reason}</p>}
                {agentTrace.summary && <p className="text-sm text-slate-200 mt-0.5">{agentTrace.summary}</p>}
                {agentTrace.verified_result !== undefined && <details className="mt-2"><summary className="text-xs text-indigo-300 cursor-pointer">Show verified result</summary><pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-[11px] text-slate-300">{JSON.stringify(agentTrace.verified_result, null, 2)}</pre></details>}
              </div>
            </div>
            <button onClick={() => setAgentTrace(null)} className="text-xs text-slate-400 hover:text-white">
              Dismiss
            </button>
          </div>
        )}

        {preview && (
          <section role="dialog" aria-modal="true" aria-label="Review import preview" className="fixed inset-0 z-50 bg-black/75 overflow-y-auto p-4">
            <div className="max-w-5xl mx-auto my-8 rounded-2xl border border-slate-700 bg-slate-900 p-5 space-y-4">
              <div className="flex justify-between gap-4"><div><h2 className="text-lg font-bold">Review {preview.source} import</h2><p className="text-xs text-slate-400">{preview.filename || "Pasted SMS"}: {preview.parsed_count} parsed · {preview.ignored_count} filtered · {preview.rejected_count} rows need attention · {preview.duplicate_count} duplicates</p></div><button onClick={() => setPreview(null)} className="text-slate-300">Close</button></div>
              {preview.issues.length > 0 && <div className="max-h-28 overflow-auto text-xs text-amber-200">{preview.issues.map((issue, i) => <p key={i}>Row {issue.row ?? "—"}: {issue.message}</p>)}</div>}
              <div className="max-h-[55vh] overflow-auto rounded-xl border border-slate-800"><table className="w-full text-left text-xs"><thead className="sticky top-0 bg-slate-950 text-slate-400"><tr><th className="p-2">Include</th><th className="p-2">Date</th><th className="p-2">Merchant / description</th><th className="p-2">Amount</th><th className="p-2">Suggested category</th><th className="p-2">Status</th></tr></thead><tbody className="divide-y divide-slate-800">{preview.transactions.map((row) => <tr key={row.row_number}><td className="p-2"><input aria-label={`Include row ${row.row_number}`} type="checkbox" disabled={row.duplicate} checked={acceptedRows.includes(row.row_number)} onChange={(e) => setAcceptedRows((old) => e.target.checked ? [...old, row.row_number] : old.filter((n) => n !== row.row_number))} /></td><td className="p-2">{row.date || <input type="date" aria-label={`Date for row ${row.row_number}`} value={dateOverrides[row.row_number] || ""} onChange={(e) => setDateOverrides({ ...dateOverrides, [row.row_number]: e.target.value })} className="bg-slate-950 border border-slate-700 rounded p-1" />}</td><td className="p-2"><strong>{row.merchant}</strong><div className="text-slate-500 max-w-xs truncate">{row.raw_narration}</div>{row.security_flag && <span className="text-amber-300">Needs narration review</span>}</td><td className="p-2">{row.txn_type} ₹{Number(row.amount).toLocaleString("en-IN")}</td><td className="p-2">{row.suggested_category}</td><td className="p-2">{row.duplicate ? "Duplicate" : "Ready"}</td></tr>)}</tbody></table></div>
              <div className="flex justify-end gap-2"><button onClick={() => setPreview(null)} className="px-3 py-2 rounded-lg bg-slate-800">Discard preview</button><button onClick={() => void confirmImport()} className="px-3 py-2 rounded-lg bg-indigo-600">Save selected rows ({acceptedRows.length})</button></div>
            </div>
          </section>
        )}

        {/* TAB 1: LIVING OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            <div className="flex justify-between items-center">
              <label className="text-xs text-slate-400 flex items-center gap-2"><input type="checkbox" checked={coverageConfirmed} onChange={(e) => void setCoverage(e.target.checked)} /> I confirmed the {selectedMonth} statement is complete</label>
              {!PUBLIC_DEMO && <button onClick={openProfileEditor} className="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm font-medium">Edit Profile &amp; Goals</button>}
            </div>
            {/* Proactive Drift Nudges */}
            {data.nudges.map((n, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
                <div>
                  <h3 className="text-sm font-bold text-amber-300">{n.title}</h3>
                  <p className="text-sm text-slate-300 mt-0.5">{n.message}</p>
                </div>
              </div>
            ))}

            {/* Top KPI Cards */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Modeled Monthly Surplus</div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-3xl font-extrabold text-emerald-400">₹{Number(data.summary.modeled_surplus ?? 0).toLocaleString("en-IN")}</span>
                </div>
                <p className="text-xs text-slate-400 mt-2">Income minus modeled fixed costs and observed variable debits</p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Monthly Income vs Outflow</div>
                <div className="mt-2 text-2xl font-bold text-white">
                  ₹{Number(data.summary.observed_income ?? 0).toLocaleString("en-IN")}
                </div>
                <p className="text-xs text-rose-400 mt-2">
                  {selectedMonth} expenses after refunds: ₹{Number(data.total_spent ?? 0).toLocaleString("en-IN")}
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Emergency Runway Buffer</div>
                <div className="mt-2 text-2xl font-bold text-cyan-400">
                  ₹{(data.profile.emergency_fund_current ?? 0).toLocaleString("en-IN")}
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full mt-2.5 overflow-hidden">
                  <div
                    className="bg-cyan-400 h-full"
                    style={{ width: `${Math.min(100, ((data.profile.emergency_fund_current ?? 0) / Math.max(data.profile.emergency_fund_target ?? 0, 1)) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Target: ₹{(data.profile.emergency_fund_target ?? 0).toLocaleString("en-IN")}
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Observed savings rate</div>
                <div className="mt-2 text-2xl font-bold text-indigo-400">{data.summary.net_observed_savings === null || Number(data.summary.observed_income ?? 0) <= 0 ? "Unavailable" : `${(Number(data.summary.net_observed_savings) / Number(data.summary.observed_income) * 100).toFixed(1)}%`}</div>
                <p className="text-xs text-slate-400 mt-2">Based on imported credits and net expenses for {selectedMonth}; statement completeness may be unknown.</p>
              </div>
            </div>

            {/* Goals & Subscriptions Worth Reviewing */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Persistent Goals */}
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-base font-bold text-white">Persistent Financial Goals</h2>
                  <button
                    onClick={() => setActiveTab("simulator")}
                    className="text-xs text-indigo-400 hover:underline cursor-pointer"
                  >
                    Simulate What-If →
                  </button>
                </div>
                {data.goals.map((g) => {
                  const savedAmount = g.saved_amount ?? 0;
                  const targetAmount = g.target_amount ?? 0;
                  const pct = Math.min(100, Math.round((savedAmount / Math.max(targetAmount, 1)) * 100));
                  return (
                    <div key={g.id} className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
                      <div className="flex justify-between text-sm font-semibold">
                        <span>{g.name}</span>
                        <span className="text-indigo-300">Target: {g.target_date}</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2.5 rounded-full overflow-hidden">
                        <div className="bg-indigo-500 h-full" style={{ width: `${pct}%` }} />
                      </div>
                      <div className="flex justify-between text-xs text-slate-400">
                        <span>Saved: ₹{(savedAmount ?? 0).toLocaleString("en-IN")} ({pct}%)</span>
                        <span>Goal: ₹{(targetAmount ?? 0).toLocaleString("en-IN")}</span>
                      </div>
                    </div>
                  );
                })}

                {/* Category Spend Chart */}
                <div className="pt-2">
                  <h3 className="text-xs font-semibold uppercase text-slate-400 mb-3">Spend Distribution (Excluding P2P Transfers)</h3>
                  <div className="h-48">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={data.category_breakdown}>
                        <XAxis dataKey="name" tick={{ fill: "#94a3b8", fontSize: 11 }} />
                        <YAxis tick={{ fill: "#94a3b8", fontSize: 11 }} />
                        <Tooltip contentStyle={{ backgroundColor: "#0f172a", borderColor: "#334155" }} />
                        <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                          {data.category_breakdown.map((_, i) => (
                            <Cell key={i} fill={COLORS[i % COLORS.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              </div>

              {/* Recurring & Subscriptions Worth Reviewing */}
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
                <div>
                  <h2 className="text-base font-bold text-white">Recurring Payments & Subscriptions Worth Reviewing</h2>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Honest signal detection: we cannot observe app usage automatically—confirm whether you still use flagged services.
                  </p>
                </div>

                <div className="space-y-3">
                  {data.recurring_alerts.length === 0 && (
                  <p className="text-sm text-slate-400">At least two dated payments with a supported cadence are needed to suggest a recurring pattern.</p>
                  )}
                  {data.recurring_alerts.map((sub, idx) => (
                    <div
                      key={idx}
                      className={`p-4 rounded-xl border ${
                        sub.type === "PRICE_HIKE"
                          ? "bg-rose-500/10 border-rose-500/30"
                          : sub.type === "WORTH_REVIEWING"
                          ? "bg-amber-500/10 border-amber-500/30"
                          : "bg-slate-950 border-slate-800"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-bold text-sm text-white">{sub.merchant}</span>
                        <span className="text-xs font-semibold px-2 py-0.5 rounded bg-slate-800 text-slate-200">
                          ₹{sub.monthly_amount}/mo (₹{(sub.annual_cost ?? 0).toLocaleString("en-IN")}/yr)
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1.5">{sub.reason}</p>
                      <div className="mt-3 flex items-center gap-2 text-xs">
                        <span className="text-slate-400">Still use this?</span>
                        {SUBSCRIPTION_OPTIONS.map((opt) => (
                          <button
                            key={opt}
                            onClick={() => handleSubFeedback(sub.merchant, opt)}
                            className={`px-2.5 py-1 rounded capitalize cursor-pointer ${
                              sub.still_uses === opt
                                ? "bg-indigo-600 text-white font-semibold"
                                : "bg-slate-800 text-slate-300 hover:bg-slate-700"
                            }`}
                          >
                            {opt}
                          </button>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {profileOpen && profileDraft && goalDraft && !PUBLIC_DEMO && (
          <div className="fixed inset-0 z-50 bg-black/70 flex items-center justify-center p-4" role="dialog" aria-modal="true" aria-label="Edit profile and goal">
            <div className="w-full max-w-xl rounded-2xl border border-slate-700 bg-slate-900 p-6 space-y-4">
              <div className="flex justify-between items-center"><h2 className="text-lg font-bold">Edit Profile &amp; Goals</h2><button onClick={() => setProfileOpen(false)} aria-label="Close">✕</button></div>
              <div className="grid grid-cols-2 gap-3">
                {PROFILE_FIELDS.map(({ label, key }) => (
                  <label key={key} className="text-xs text-slate-400">{label}<input type="number" value={profileDraft[key] ?? 0} onChange={(e) => setProfileDraft({ ...profileDraft, [key]: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                ))}
              </div>
              <h3 className="text-sm font-semibold text-slate-200">Primary goal</h3>
              <div className="flex gap-2">
                <select value={goalDraft.id ?? "new"} onChange={(e) => {
                  if (e.target.value === "new") {
                    setGoalDraft({ name: "", target_amount: 0, saved_amount: 0, target_date: "", priority: 1 });
                  } else {
                    const selected = data.goals.find((goal) => goal.id === Number(e.target.value));
                    if (selected) setGoalDraft({ ...selected });
                  }
                }} className="flex-1 rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white">
                  {data.goals.map((goal) => <option key={goal.id} value={goal.id}>{goal.name}</option>)}
                  <option value="new">Add a goal…</option>
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <label className="text-xs text-slate-400 col-span-2">Goal name<input value={goalDraft.name ?? ""} onChange={(e) => setGoalDraft({ ...goalDraft, name: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                <label className="text-xs text-slate-400">Target amount<input type="number" value={goalDraft.target_amount ?? 0} onChange={(e) => setGoalDraft({ ...goalDraft, target_amount: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                <label className="text-xs text-slate-400">Saved so far<input type="number" value={goalDraft.saved_amount ?? 0} onChange={(e) => setGoalDraft({ ...goalDraft, saved_amount: Number(e.target.value) })} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
                <label className="text-xs text-slate-400">Target date<input type="date" value={goalDraft.target_date ?? ""} onChange={(e) => setGoalDraft({ ...goalDraft, target_date: e.target.value })} className="mt-1 w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-white" /></label>
              </div>
              <div className="flex justify-end gap-2"><button onClick={() => setProfileOpen(false)} className="px-3 py-2 rounded-lg bg-slate-800">Cancel</button><button onClick={saveProfileAndGoal} className="px-3 py-2 rounded-lg bg-indigo-600 font-semibold">Save changes</button></div>
            </div>
          </div>
        )}

        {/* TAB 2: LEDGER, INGESTION & RULE LEARNING LOOP */}
        {activeTab === "ledger" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {/* Messy Ingestion Box */}
              <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-bold text-white">Ingest Messy Statements (PDF / CSV) or Bank SMS</h3>
                  <label className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium cursor-pointer flex items-center gap-1.5">
                    <Upload className="w-3.5 h-3.5" /> Upload PDF / CSV / SMS text
                    <input type="file" accept=".pdf,.csv,.txt" onChange={handleFileUpload} className="hidden" />
                  </label>
                </div>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={smsText}
                    onChange={(e) => setSmsText(e.target.value)}
                    placeholder="Paste raw Indian bank SMS (e.g. Rs. 650 debited to VPA swiggyinstamart@icici...)"
                    className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-3 py-2 text-xs text-white"
                  />
                  <button
                    onClick={handleSmsSubmit}
                    className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-xs font-semibold cursor-pointer"
                  >
                    Parse SMS
                  </button>
                </div>
                {ingestBanner && <p className="text-xs text-emerald-400">{ingestBanner}</p>}
                <div className="flex flex-wrap gap-2 text-xs"><a className="px-3 py-1.5 rounded bg-slate-800" href={`${API}/transactions/export.csv`}>Export transactions CSV</a><a className="px-3 py-1.5 rounded bg-slate-800" href={`${API}/data/export.json`}>Export data JSON</a>{!PUBLIC_DEMO && <button className="px-3 py-1.5 rounded bg-rose-950 text-rose-200" onClick={async () => { if (window.confirm("Permanently delete all ArthaTwin transactions, rules, goals and imports?")) { const response = await fetch(`${API}/data`, { method: "DELETE", headers: { "X-Confirm-Delete": "DELETE ARTHATWIN DATA" } }); if (response.ok) { setIngestBanner("Your local ArthaTwin data was deleted."); await fetchDashboard(); } else setError("Data deletion failed."); } }}>Delete all data…</button>}</div>
              </div>

              {/* Editable Transactions Table */}
              <div className="rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden">
                <div className="p-4 border-b border-slate-800 flex justify-between items-center">
                  <div>
                    <h2 className="text-sm font-bold text-white">Transaction Ledger (Click Category to Teach Rule)</h2>
                    <p className="text-xs text-slate-400">Try changing SWIGGY INSTAMART from Dining Out → Groceries to trigger live rule learning.</p>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-slate-950 text-slate-400 uppercase">
                      <tr>
                        <th className="p-3">Date / Src</th>
                        <th className="p-3">Merchant & Raw Narration</th>
                        <th className="p-3">Amount</th>
                        <th className="p-3">Category (Editable)</th>
                        <th className="p-3">Engine Source</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800">
                      {data.transactions.map((t) => (
                        <tr key={t.id} className="hover:bg-slate-800/40">
                          <td className="p-3 whitespace-nowrap">
                            <div className="font-medium text-slate-200">{t.date}</div>
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">{t.source}</span>
                          </td>
                          <td className="p-3">
                            <div className="font-bold text-white flex items-center gap-1.5">
                              {t.merchant}
                              {t.user_locked && <Lock className="w-3 h-3 text-emerald-400" />}
                            </div>
                            <div className="text-[11px] text-slate-400 truncate max-w-xs">{t.raw_narration}</div>
                            {t.security_flag && (
                              <span className="inline-flex items-center gap-1 mt-1 text-[10px] px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/40">
                                <ShieldAlert className="w-3 h-3" /> {t.security_flag}
                              </span>
                            )}
                          </td>
                          <td className={`p-3 font-bold whitespace-nowrap ${t.txn_type === "CREDIT" ? "text-emerald-400" : "text-slate-100"}`}>
                            {t.txn_type === "CREDIT" ? "+" : "-"}₹{(t.amount ?? 0).toLocaleString("en-IN")}
                          </td>
                          <td className="p-3">
                            <select
                              value={t.category}
                              onChange={(e) => handleCategoryFix(t.id, e.target.value)}
                              className="bg-slate-950 border border-slate-700 rounded px-2 py-1 text-xs text-white cursor-pointer"
                            >
                              {CATEGORIES.map((c) => (
                                <option key={c} value={c}>{c}</option>
                              ))}
                            </select>
                          </td>
                          <td className="p-3">
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                                t.confidence_source === "LEARNED_RULE"
                                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                                  : "bg-slate-800 text-slate-300"
                              }`}
                            >
                              {t.confidence_source}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>

            {/* Right Sidebar: Learned Rules Memory */}
            <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4 h-fit">
              <div className="flex items-center gap-2">
                <Brain className="w-5 h-5 text-indigo-400" />
                <h2 className="text-sm font-bold text-white">AI Learned Rule Memory</h2>
              </div>
              <p className="text-xs text-slate-400">
                Every user correction compiles into a deterministic rule with higher precedence than default heuristics.
              </p>
              {data.learned_rules.length === 0 ? (
                <div className="p-4 rounded-xl bg-slate-950 border border-dashed border-slate-800 text-xs text-slate-400">
                  No custom rules learned yet. Change any transaction category on the left to watch the system learn!
                </div>
              ) : (
                <div className="space-y-2.5">
              {data.learned_rules.map((r) => (
                    <div key={r.id} className="p-3 rounded-xl bg-slate-950 border border-emerald-500/30 space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-emerald-300">MATCH: &quot;{r.pattern}&quot;{!r.is_enabled && " (disabled)"}</span>
                        <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">{r.matching_count} unlocked matches · {r.hit_count} corrections</span>
                      </div>
                      <div className="text-xs text-white font-medium">→ Assign Category: {r.category}</div>
                      <div className="text-[11px] text-slate-400">{r.explanation}</div>
                      <button onClick={async () => { const response = await fetch(`${API}/rules/${r.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !r.is_enabled }) }); if (response.ok) await fetchDashboard(); else setError("Could not update rule."); }} className="text-xs text-indigo-300 underline">{r.is_enabled ? "Disable rule" : "Enable rule"}</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB 3: WHAT-IF GOAL SIMULATOR */}
        {activeTab === "simulator" && simResult && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
              <div>
                <h2 className="text-base font-bold text-white">Interactive &quot;What-If&quot; Cashflow Simulator</h2>
                <p className="text-xs text-slate-400 mt-0.5">Adjust lifestyle levers to see real-time impact on your goal dates.</p>
              </div>

              <div className="space-y-4">
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Cut Dining Out Spend</span>
                    <span className="font-bold text-emerald-400">-{diningCut}%</span>
                  </div>
                  <input
                    type="range" min={0} max={60} step={5} value={diningCut}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setDiningCut(v);
                      runSimulation(v, rentChange, cancelSubs, extraIncome);
                    }}
                    className="w-full accent-indigo-500"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Rent Increase / Housing Shift</span>
                    <span className="font-bold text-rose-400">+₹{(rentChange ?? 0).toLocaleString("en-IN")}/mo</span>
                  </div>
                  <input
                    type="range" min={0} max={15000} step={1000} value={rentChange}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setRentChange(v);
                      runSimulation(diningCut, v, cancelSubs, extraIncome);
                    }}
                    className="w-full accent-rose-500"
                  />
                </div>

                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>Monthly income change</span>
                    <span className="font-bold text-cyan-400">{extraIncome >= 0 ? "+" : "−"}₹{Math.abs(extraIncome).toLocaleString("en-IN")}/mo</span>
                  </div>
                  <input
                    type="range" min={-30000} max={30000} step={2500} value={extraIncome}
                    onChange={(e) => {
                      const v = Number(e.target.value);
                      setExtraIncome(v);
                      runSimulation(diningCut, rentChange, cancelSubs, v);
                    }}
                    className="w-full accent-cyan-500"
                  />
                </div>

                <label className="flex items-center gap-3 p-3 rounded-xl bg-slate-950 border border-slate-800 cursor-pointer">
                  <input
                    type="checkbox" checked={cancelSubs}
                    onChange={(e) => {
                      setCancelSubs(e.target.checked);
                      runSimulation(diningCut, rentChange, e.target.checked, extraIncome);
                    }}
                    className="w-4 h-4 accent-indigo-500"
                  />
                  <span className="text-sm">Model cancellation of subscriptions you marked “No” (+₹{Number(simResult?.subscription_savings ?? 0).toLocaleString("en-IN")}/mo)</span>
                </label>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5">
              <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div>
                  <div className="text-xs text-slate-400">Simulated Monthly Surplus</div>
                  <div className="text-2xl font-extrabold text-white">
                    ₹{(simResult.simulated_monthly_surplus ?? 0).toLocaleString("en-IN")}/mo
                  </div>
                </div>
                <div className={`text-sm font-bold px-3 py-1 rounded-full ${simResult.monthly_delta >= 0 ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                  {simResult.monthly_delta >= 0 ? "+" : ""}₹{(simResult.monthly_delta ?? 0).toLocaleString("en-IN")}/mo vs baseline
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase text-slate-400">Goal Timeline Impact (&quot;Time-Tax&quot; Delta)</h3>
                {simResult.goal_impacts.map((g, idx) => {
                  const hasTimeline = g.days_saved !== null;
                  const daysSaved = g.days_saved ?? 0;
                  return <div key={idx} className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                    <div>
                      <div className="font-bold text-sm text-white">{g.goal_name}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        New Projected Completion: <span className="text-indigo-300 font-semibold">{g.projected_completion ?? "Unavailable"}</span> ({g.new_months ?? "—"} mos)
                      </div>
                    </div>
                    <div className={`text-xs font-bold px-3 py-1.5 rounded-lg ${hasTimeline ? daysSaved >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300" : "bg-slate-800 text-slate-400"}`}>
                      {!hasTimeline ? "Timeline unavailable" : daysSaved >= 0 ? `${daysSaved} days faster` : `${Math.abs(daysSaved)} days delayed`}
                    </div>
                  </div>;
                })}
              </div>
              <p className="text-[11px] text-slate-500">{simResult.assumptions}</p>
            </div>
          </div>
        )}

        {/* TAB 4: GUARDRAILED COACH */}
        {activeTab === "coach" && (
          <div className="max-w-3xl mx-auto p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div>
                <h2 className="text-base font-bold text-white">Guardrailed Financial Coach</h2>
                <p className="text-xs text-slate-400">Models scenarios from your verified state. Hard-blocked from recommending stocks or funds.</p>
              </div>
              <button
                onClick={() => handleSendChat("Which mid-cap mutual fund or stock should I buy with my surplus?")}
                className="px-3 py-1.5 rounded-lg bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 text-xs font-semibold cursor-pointer"
              >
                🧪 Test Guardrail (Ask for Stock Tip)
              </button>
            </div>

            <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
              {messages.map((m, idx) => (
                <div
                  key={idx}
                  className={`p-3.5 rounded-xl text-sm leading-relaxed ${
                    m.role === "user"
                      ? "bg-indigo-600 text-white ml-12"
                      : m.guardrail
                      ? "bg-amber-500/15 border border-amber-500/40 text-amber-100 mr-8"
                      : "bg-slate-950 border border-slate-800 text-slate-200 mr-8"
                  }`}
                >
                  {m.text}
                </div>
              ))}
            </div>

            <label className="flex items-start gap-2 text-xs text-slate-400"><input type="checkbox" checked={allowExternalAi} onChange={(e) => setAllowExternalAi(e.target.checked)} /><span>Allow optional external AI to receive this question for tool selection. Stored profile, transactions, and calculated results stay on this server; the selected tool runs locally. Do not include account numbers or other sensitive identifiers. Off by default.</span></label>

            <div className="flex gap-2 pt-2">
              <input
                type="text"
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSendChat()}
                placeholder="Ask e.g. 'How can I reach my MacBook goal 2 months faster?'"
                className="flex-1 bg-slate-950 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-white"
              />
              <button
                onClick={() => handleSendChat()}
                className="px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold flex items-center gap-1.5 cursor-pointer"
              >
                <Send className="w-4 h-4" /> Send
              </button>
            </div>
          </div>
        )}

        {/* TAB 5: MONTHLY REVIEW REPORT */}
        {activeTab === "report" && (
          <div className="max-w-4xl mx-auto p-4 sm:p-8 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-bold">
                  Monthly review • {report?.month ?? selectedMonth}
                </span>
                <h2 className="text-2xl font-bold text-white mt-1">Monthly Financial Health & Action Review</h2>
              </div>
              <button
                onClick={() => window.print()}
                className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-semibold flex items-center gap-2 cursor-pointer"
              >
                <Printer className="w-4 h-4" /> Export / Print PDF
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Observed income</div>
                <div className="text-xl font-bold text-emerald-400 mt-1">₹{formatINR(report?.income)}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Observed expenses, net of refunds</div>
                <div className="text-xl font-bold text-rose-400 mt-1">₹{formatINR(report?.expenses)}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Observed net savings</div>
                <div className="text-xl font-bold text-cyan-300 mt-1">{report?.observed_savings === null || report?.observed_savings === undefined ? "Unavailable" : "₹" + formatINR(report.observed_savings)}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Modeled monthly surplus</div>
                <div className="text-xl font-bold text-indigo-400 mt-1">₹{formatINR(report?.modeled_surplus)}</div>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">1. Recurring payments to review</h3>
              <ul className="list-disc pl-5 text-sm text-slate-300 space-y-1">
                {(report?.recurring_payments ?? []).map((a, i) => (
                  <li key={i}><strong>{a.merchant}:</strong> {a.reason}</li>
                ))}
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">2. Spending changes</h3>
              {(report?.spending_changes ?? []).length === 0 ? <p className="text-sm text-slate-400">No category change passed the review threshold, or both statement months are not confirmed complete.</p> : (report?.spending_changes ?? []).map((item, i) => <p key={i} className="text-sm text-slate-300"><strong>{item.title}:</strong> {item.message}</p>)}
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">3. Goal progress</h3>
              {(report?.goals ?? []).length === 0 ? <p className="text-sm text-slate-400">No saved goals for this profile.</p> : (report?.goals ?? []).map((goal) => <p key={goal.name} className="text-sm text-slate-300">{goal.name}: ₹{formatINR(goal.saved_amount)} of ₹{formatINR(goal.target_amount)} · target {goal.target_date}</p>)}
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">4. Rule-Learning Memory Updates</h3>
              <p className="text-sm text-slate-300">
                {data.learned_rules.length > 0
                  ? `Active custom rules learned from your corrections: ${data.learned_rules.map((r) => `${r.pattern} → ${r.category}`).join(", ")}.`
                  : "All transactions categorized via deterministic merchant rules and P2P filters."}
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-5"><section><h3 className="text-sm font-bold">Category breakdown</h3>{(report?.category_breakdown ?? []).map((item) => <p key={item.name} className="text-sm text-slate-300">{item.name}: ₹{Number(item.value).toLocaleString("en-IN")}</p>)}</section><section><h3 className="text-sm font-bold">Data quality and assumptions</h3><p className="text-xs text-slate-400">Profile income assumption: ₹{Number(report?.profile_income_assumption ?? 0).toLocaleString("en-IN")}. Savings figure is modeled, not verified account balance.</p>{(report?.data_quality.warnings ?? data.data_quality_warnings).map((warning, i) => <p key={i} className="text-xs text-amber-300">{warning}</p>)}</section></div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{data.disclaimer}</span>
            </div>
          </div>
        )}

        {activeTab === "settings" && (
          <section className="max-w-3xl mx-auto p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5">
            <div><h2 className="text-xl font-bold">Privacy, settings &amp; data</h2><p className="text-sm text-slate-400 mt-1">ArthaTwin stores the profile and imported records in its configured database. No bank connection is made.</p></div>
            <div className="rounded-xl bg-slate-950 border border-slate-800 p-4 text-sm space-y-2"><p><strong>AI:</strong> deterministic coaching is the default. If enabled by the server and opted in per question, the question text is sent to Google for tool selection; profile, transaction data, tool results and raw narration stay on this server.</p><p><strong>Financial safety:</strong> educational planning only; no security recommendations, guaranteed returns or money movement.</p><p><strong>Current mode:</strong> {PUBLIC_DEMO ? "Shared synthetic-data demo. Personal imports, profile edits and deletion are blocked; demo corrections are visible to other visitors." : "Single-user local mode. This instance has no login or multi-user data isolation; do not expose it publicly."}</p></div>
            <div className="flex flex-wrap gap-2"><a href={`${API}/transactions/export.csv`} className="px-4 py-2 rounded-lg bg-slate-800">Download transactions CSV</a><a href={`${API}/data/export.json`} className="px-4 py-2 rounded-lg bg-slate-800">Download data JSON</a>{!PUBLIC_DEMO && <button onClick={async () => { if (window.confirm("Permanently delete all ArthaTwin transactions, rules, goals and imports?")) { const response = await fetch(`${API}/data`, { method: "DELETE", headers: { "X-Confirm-Delete": "DELETE ARTHATWIN DATA" } }); if (response.ok) { setIngestBanner("Your local ArthaTwin data was deleted."); await fetchDashboard(); } else setError("Data deletion failed."); } }} className="px-4 py-2 rounded-lg bg-rose-950 text-rose-200">Delete all data…</button>}</div>
            <p className="text-xs text-slate-500">External AI consent is asked in the coach for each session setting and defaults off. Profile values are user-provided assumptions; transaction aggregates may be incomplete.</p>
          </section>
        )}
      </main>
    </div>
  );
}
