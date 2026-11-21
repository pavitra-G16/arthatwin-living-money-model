import Link from "next/link";

export default function LandingPage() {
  return (
    <main className="min-h-screen bg-gradient-to-br from-slate-950 via-indigo-950 to-slate-950 text-white flex items-center">
      <section className="max-w-5xl mx-auto px-6 py-20 grid md:grid-cols-2 gap-12 items-center">
        <div className="space-y-6">
          <span className="inline-flex rounded-full border border-emerald-400/30 bg-emerald-400/10 px-3 py-1 text-xs text-emerald-200">INTELLIGENCE BEHIND EVERY RUPEE</span>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight">A clearer model of your money.</h1>
          <p className="text-lg text-slate-300">Bring a statement, review every imported transaction, then explore practical choices with transparent calculations and a careful finance coach.</p>
          <div className="flex flex-wrap gap-3"><Link href="/demo" className="rounded-xl bg-indigo-500 px-5 py-3 font-semibold hover:bg-indigo-400">Explore the demo</Link><Link href="/" className="rounded-xl border border-slate-600 px-5 py-3 font-semibold hover:bg-slate-800">Open dashboard</Link></div>
          <p className="text-xs text-slate-500">Educational planning only. No bank connection, investment recommendations or money movement.</p>
        </div>
        <div className="rounded-3xl border border-indigo-400/20 bg-slate-900/80 p-8 shadow-2xl shadow-indigo-950/60"><div className="text-sm text-indigo-200">LIVING MONEY MODEL</div><div className="mt-5 grid grid-cols-2 gap-3">{[["Import", "CSV · PDF · SMS"], ["Understand", "Period-aware cashflow"], ["Plan", "Deterministic scenarios"], ["Review", "Goals · nudges · reports"]].map(([title, detail]) => <div key={title} className="rounded-xl bg-slate-950 p-4"><div className="font-semibold">{title}</div><div className="mt-1 text-xs text-slate-400">{detail}</div></div>)}</div><p className="mt-5 text-xs leading-5 text-slate-400">Imported amounts, user assumptions and modeled estimates are shown separately. Statement completeness is never inferred from a few transaction rows.</p></div>
      </section>
    </main>
  );
}
