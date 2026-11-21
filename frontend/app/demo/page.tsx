import Link from "next/link";

export default function DemoEntryPage() {
  return (
    <main className="min-h-screen bg-slate-950 text-white flex items-center justify-center px-5">
      <section className="max-w-xl rounded-3xl border border-slate-800 bg-slate-900 p-8 space-y-5">
        <span className="inline-flex rounded-full bg-amber-400/10 border border-amber-300/30 px-3 py-1 text-xs text-amber-200">FICTIONAL DATA ONLY</span>
        <h1 className="text-3xl font-bold">Enter the ArthaTwin demo</h1>
        <p className="text-sm leading-6 text-slate-300">This demo uses invented transactions and profile assumptions. Do not upload personal statements. In a hosted demo, sample data is prepared at service start; in local development, load the sample dataset from the dashboard.</p>
        <Link href="/" className="inline-flex rounded-xl bg-indigo-500 px-5 py-3 font-semibold hover:bg-indigo-400">Continue to dashboard</Link>
        <p className="text-xs text-slate-500">Authentication is not configured. The public demo is a shared synthetic workspace, not a private account.</p>
      </section>
    </main>
  );
}
