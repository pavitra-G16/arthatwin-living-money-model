"use client";

import React, { useState, useEffect } from "react";
import {
  Sparkles, ShieldAlert, TrendingUp, Brain, Sliders, MessageSquare,
  FileText, Upload, CheckCircle2, AlertTriangle, RefreshCw, Lock, Printer, Send
} from "lucide-react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell
} from "recharts";

const API = "http://127.0.0.1:8000/api";

const CATEGORIES = [
  "Dining Out", "Groceries", "Transport", "Travel", "Subscriptions",
  "Utilities", "Housing", "Health", "Shopping", "Transfers / People", "Income"
];

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ec4899", "#06b6d4", "#8b5cf6", "#f43f5e"];

export default function ArthaTwinDashboard() {
  const [data, setData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<"overview" | "ledger" | "simulator" | "coach" | "report">("overview");
  const [loading, setLoading] = useState(false);
  const [agentTrace, setAgentTrace] = useState<any>(null);

  // Ingestion states
  const [smsText, setSmsText] = useState("");
  const [ingestBanner, setIngestBanner] = useState("");

  // Simulator states
  const [diningCut, setDiningCut] = useState(30);
  const [rentChange, setRentChange] = useState(0);
  const [cancelSubs, setCancelSubs] = useState(true);
  const [extraIncome, setExtraIncome] = useState(0);
  const [simResult, setSimResult] = useState<any>(null);

  // Coach states
  const [chatInput, setChatInput] = useState("");
  const [messages, setMessages] = useState<Array<{ role: string; text: string; guardrail?: boolean }>>([
    {
      role: "assistant",
      text: "Namaste! I am ArthaTwin, your Living Money Model coach. Load your bank statements or click 'Load Sample Indian Bank Data' above, then ask me about spending trade-offs or goal timelines."
    }
  ]);

  const fetchDashboard = async () => {
    try {
      const res = await fetch(`${API}/dashboard`);
      const json = await res.json();
      setData(json);
    } catch (e) {
      console.error("Backend not reachable", e);
    }
  };

  const runSimulation = async (dCut = diningCut, rChg = rentChange, cSubs = cancelSubs, eInc = extraIncome) => {
    try {
      const res = await fetch(`${API}/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dining_cut_pct: dCut,
          rent_change: rChg,
          cancel_unused_subs: cSubs,
          extra_income: eInc
        })
      });
      setSimResult(await res.json());
    } catch (e) {
      console.error(e);
    }
  };

  useEffect(() => {
    fetchDashboard();
    runSimulation();
  }, []);

  const handleSeedDemo = async () => {
    setLoading(true);
    await fetch(`${API}/seed-demo`, { method: "POST" });
    await fetchDashboard();
    await runSimulation();
    setAgentTrace({
      event: "MULTI_FORMAT_INGESTION_COMPLETE",
      summary: "Ingested 16 messy Indian transactions across PDF, CSV, and SMS. Quarantined 1 prompt-injection narration and flagged 2 recurring subscription anomalies."
    });
    setLoading(false);
  };

  const handleCategoryFix = async (txnId: number, newCategory: string) => {
    const res = await fetch(`${API}/transactions/${txnId}/correct`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_category: newCategory })
    });
    const json = await res.json();
    if (json.agent_trace) {
      setAgentTrace(json.agent_trace);
    }
    await fetchDashboard();
    await runSimulation();
  };

  const handleSubFeedback = async (merchant: string, still_uses: string) => {
    await fetch(`${API}/subscriptions/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ merchant, still_uses })
    });
    await fetchDashboard();
  };

  const handleSmsSubmit = async () => {
    if (!smsText.trim()) return;
    const res = await fetch(`${API}/ingest/sms`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sms_text: smsText })
    });
    const json = await res.json();
    setIngestBanner(`Parsed ${json.ingested} transaction SMS (filtered out ${json.ignored_otp_promo} OTP/promo messages).`);
    setSmsText("");
    await fetchDashboard();
    await runSimulation();
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.[0]) return;
    const formData = new FormData();
    formData.append("file", e.target.files[0]);
    const res = await fetch(`${API}/ingest/file`, { method: "POST", body: formData });
    const json = await res.json();
    setIngestBanner(`Ingested ${json.ingested} rows from ${e.target.files[0].name}.`);
    await fetchDashboard();
    await runSimulation();
  };

  const handleSendChat = async (customPrompt?: string) => {
    const query = customPrompt || chatInput;
    if (!query.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: query }]);
    setChatInput("");
    const res = await fetch(`${API}/coach`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: query })
    });
    const json = await res.json();
    setMessages((prev) => [
      ...prev,
      { role: "assistant", text: json.reply, guardrail: json.guardrail_triggered }
    ]);
  };

  if (!data) {
    return (
      <div className="min-h-screen bg-slate-950 text-white flex items-center justify-center">
        <div className="text-center space-y-3">
          <RefreshCw className="w-8 h-8 animate-spin mx-auto text-indigo-400" />
          <p className="text-slate-300">Connecting to ArthaTwin Living Money Engine (Port 8000)...</p>
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
            <button
              onClick={handleSeedDemo}
              disabled={loading}
              className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold flex items-center gap-2 shadow-lg shadow-indigo-600/25 transition cursor-pointer"
            >
              <Sparkles className="w-4 h-4" />
              {loading ? "Loading..." : "Load Sample Indian Bank Data"}
            </button>
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
          ].map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
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
        {/* Live Agent Trace Banner */}
        {agentTrace && (
          <div className="p-3.5 rounded-xl bg-indigo-950/70 border border-indigo-500/40 flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <Brain className="w-5 h-5 text-indigo-400 mt-0.5 shrink-0" />
              <div>
                <div className="text-xs font-bold uppercase tracking-wider text-indigo-300">
                  Agent Trace • {agentTrace.event}
                </div>
                <p className="text-sm text-slate-200 mt-0.5">{agentTrace.summary}</p>
              </div>
            </div>
            <button onClick={() => setAgentTrace(null)} className="text-xs text-slate-400 hover:text-white">
              Dismiss
            </button>
          </div>
        )}

        {/* TAB 1: LIVING OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Proactive Drift Nudges */}
            {data.nudges.map((n: any, idx: number) => (
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
                <div className="text-xs text-slate-400 uppercase font-semibold">Living Health Score</div>
                <div className="mt-2 flex items-baseline gap-2">
                  <span className="text-4xl font-extrabold text-emerald-400">{data.health_score}</span>
                  <span className="text-sm text-slate-400">/ 100</span>
                </div>
                <p className="text-xs text-slate-400 mt-2">Updates live on every import & rule fix</p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Monthly Income vs Outflow</div>
                <div className="mt-2 text-2xl font-bold text-white">
                  ₹{data.profile.monthly_income.toLocaleString("en-IN")}
                </div>
                <p className="text-xs text-rose-400 mt-2">
                  Tracked Outflow: ₹{Math.round(data.total_spent).toLocaleString("en-IN")}
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Emergency Runway Buffer</div>
                <div className="mt-2 text-2xl font-bold text-cyan-400">
                  ₹{data.profile.emergency_fund_current.toLocaleString("en-IN")}
                </div>
                <div className="w-full bg-slate-800 h-2 rounded-full mt-2.5 overflow-hidden">
                  <div
                    className="bg-cyan-400 h-full"
                    style={{ width: `${Math.min(100, (data.profile.emergency_fund_current / data.profile.emergency_fund_target) * 100)}%` }}
                  />
                </div>
                <p className="text-xs text-slate-400 mt-1">
                  Target: ₹{data.profile.emergency_fund_target.toLocaleString("en-IN")}
                </p>
              </div>

              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400 uppercase font-semibold">Learned Memory Rules</div>
                <div className="mt-2 text-2xl font-bold text-indigo-400">{data.learned_rules.length} Active</div>
                <p className="text-xs text-slate-400 mt-2">
                  {data.transactions.length} transactions synced (PDF/CSV/SMS)
                </p>
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
                {data.goals.map((g: any) => {
                  const pct = Math.min(100, Math.round((g.saved_amount / g.target_amount) * 100));
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
                        <span>Saved: ₹{g.saved_amount.toLocaleString("en-IN")} ({pct}%)</span>
                        <span>Goal: ₹{g.target_amount.toLocaleString("en-IN")}</span>
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
                          {data.category_breakdown.map((_: any, i: number) => (
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
                    <p className="text-sm text-slate-400">Click &quot;Load Sample Indian Bank Data&quot; to detect recurring patterns.</p>
                  )}
                  {data.recurring_alerts.map((sub: any, idx: number) => (
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
                          ₹{sub.monthly_amount}/mo (₹{sub.annual_cost.toLocaleString("en-IN")}/yr)
                        </span>
                      </div>
                      <p className="text-xs text-slate-300 mt-1.5">{sub.reason}</p>
                      <div className="mt-3 flex items-center gap-2 text-xs">
                        <span className="text-slate-400">Still use this?</span>
                        {["yes", "no", "unsure"].map((opt) => (
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

        {/* TAB 2: LEDGER, INGESTION & RULE LEARNING LOOP */}
        {activeTab === "ledger" && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 space-y-4">
              {/* Messy Ingestion Box */}
              <div className="p-4 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-sm font-bold text-white">Ingest Messy Statements (PDF / CSV) or Bank SMS</h3>
                  <label className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-xs font-medium cursor-pointer flex items-center gap-1.5">
                    <Upload className="w-3.5 h-3.5" /> Upload PDF / CSV
                    <input type="file" accept=".pdf,.csv" onChange={handleFileUpload} className="hidden" />
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
                      {data.transactions.map((t: any) => (
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
                            {t.txn_type === "CREDIT" ? "+" : "-"}₹{t.amount.toLocaleString("en-IN")}
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
                  {data.learned_rules.map((r: any) => (
                    <div key={r.id} className="p-3 rounded-xl bg-slate-950 border border-emerald-500/30 space-y-1">
                      <div className="flex justify-between items-center">
                        <span className="text-xs font-bold text-emerald-300">MATCH: &quot;{r.pattern}&quot;</span>
                        <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-300">Hits: {r.hit_count}</span>
                      </div>
                      <div className="text-xs text-white font-medium">→ Assign Category: {r.category}</div>
                      <div className="text-[11px] text-slate-400">{r.explanation}</div>
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
                    <span className="font-bold text-rose-400">+₹{rentChange.toLocaleString("en-IN")}/mo</span>
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
                    <span>Extra Freelance / Side Income</span>
                    <span className="font-bold text-cyan-400">+₹{extraIncome.toLocaleString("en-IN")}/mo</span>
                  </div>
                  <input
                    type="range" min={0} max={30000} step={2500} value={extraIncome}
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
                  <span className="text-sm">Cancel flagged unused subscriptions (+₹1,499/mo saved)</span>
                </label>
              </div>
            </div>

            <div className="p-6 rounded-2xl bg-slate-900 border border-slate-800 space-y-5">
              <div className="flex items-center justify-between p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div>
                  <div className="text-xs text-slate-400">Simulated Monthly Surplus</div>
                  <div className="text-2xl font-extrabold text-white">
                    ₹{simResult.simulated_monthly_surplus.toLocaleString("en-IN")}/mo
                  </div>
                </div>
                <div className={`text-sm font-bold px-3 py-1 rounded-full ${simResult.monthly_delta >= 0 ? "bg-emerald-500/20 text-emerald-300" : "bg-rose-500/20 text-rose-300"}`}>
                  {simResult.monthly_delta >= 0 ? "+" : ""}₹{simResult.monthly_delta.toLocaleString("en-IN")}/mo vs baseline
                </div>
              </div>

              <div className="space-y-3">
                <h3 className="text-xs font-bold uppercase text-slate-400">Goal Timeline Impact (&quot;Time-Tax&quot; Delta)</h3>
                {simResult.goal_impacts.map((g: any, idx: number) => (
                  <div key={idx} className="p-4 rounded-xl bg-slate-950 border border-slate-800 flex items-center justify-between">
                    <div>
                      <div className="font-bold text-sm text-white">{g.goal_name}</div>
                      <div className="text-xs text-slate-400 mt-0.5">
                        New Projected Completion: <span className="text-indigo-300 font-semibold">{g.projected_completion}</span> ({g.new_months} mos)
                      </div>
                    </div>
                    <div className={`text-xs font-bold px-3 py-1.5 rounded-lg ${g.days_saved >= 0 ? "bg-emerald-500/15 text-emerald-300" : "bg-rose-500/15 text-rose-300"}`}>
                      {g.days_saved >= 0 ? `${g.days_saved} days faster` : `${Math.abs(g.days_saved)} days delayed`}
                    </div>
                  </div>
                ))}
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
          <div className="max-w-4xl mx-auto p-8 rounded-2xl bg-slate-900 border border-slate-800 space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <span className="text-[11px] uppercase tracking-wider text-emerald-400 font-bold">
                  Verified Deterministic Report • November 2026
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

            <div className="grid grid-cols-3 gap-4">
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Net Monthly Income</div>
                <div className="text-xl font-bold text-emerald-400 mt-1">₹{data.profile.monthly_income.toLocaleString("en-IN")}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Verified Expenses</div>
                <div className="text-xl font-bold text-rose-400 mt-1">₹{Math.round(data.total_spent).toLocaleString("en-IN")}</div>
              </div>
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800">
                <div className="text-xs text-slate-400">Living Health Score</div>
                <div className="text-xl font-bold text-indigo-400 mt-1">{data.health_score} / 100</div>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">1. Top Spending Leaks & Anomalies Detected</h3>
              <ul className="list-disc pl-5 text-sm text-slate-300 space-y-1">
                {data.recurring_alerts.map((a: any, i: number) => (
                  <li key={i}><strong>{a.merchant}:</strong> {a.reason}</li>
                ))}
              </ul>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-bold text-white">2. Rule-Learning Memory Updates</h3>
              <p className="text-sm text-slate-300">
                {data.learned_rules.length > 0
                  ? `Active custom rules learned from your corrections: ${data.learned_rules.map((r: any) => `${r.pattern} → ${r.category}`).join(", ")}.`
                  : "All transactions categorized via deterministic merchant rules and P2P filters."}
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
              <span>{data.disclaimer}</span>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
