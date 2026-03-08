"""
NotebookLM Meeting Prep Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Usage:
    python3 pipeline.py --company "Digital Gravity" --domain "digitalgravity.ae" --context "Partnership discussion"

Or set via environment variables:
    COMPANY="Acme Corp" DOMAIN="acme.com" python3 pipeline.py
"""

import asyncio
import argparse
import os
from pathlib import Path
from notebooklm import NotebookLMClient

# ── Configuration ──────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="NotebookLM Meeting Prep Pipeline")
parser.add_argument("--company", default=os.getenv("COMPANY", "Digital Gravity"), help="Company name")
parser.add_argument("--domain",  default=os.getenv("DOMAIN",  "digitalgravity.ae"), help="Company domain")
parser.add_argument("--context", default=os.getenv("CONTEXT", "Strategic Partnership discussion"), help="Meeting context")
parser.add_argument("--output",  default=os.getenv("OUTPUT",  "."), help="Output directory (default: current dir)")
parser.add_argument("--research-mode", choices=["fast", "deep"], default="fast", help="fast (~10 sources) or deep (~40-100 sources)")
args = parser.parse_args()

COMPANY = args.company
DOMAIN  = args.domain
CONTEXT = args.context
FOLDER  = os.path.join(args.output, f"Meeting Prep - {COMPANY}")
RESEARCH_MODE = args.research_mode

PROFILE = f"""
Company: {COMPANY}
Website: https://{DOMAIN}
Meeting Context: {CONTEXT}
"""

BRIEFING_PROMPT = (
    "Create a comprehensive executive pre-meeting briefing with these sections: "
    "1) Company Overview (background, size, leadership, financials, business model, core products, key clients, recent developments, meeting context), "
    "2) Competitive Landscape (name each competitor, approach, client advantage), "
    "3) Market Opportunity (dollar figures, growth rates, government initiatives), "
    "4) Key Talking Points (numbered, actionable), "
    "5) Handling Objections (table: Objection | Response), "
    "6) Recommended Next Steps (3 concrete actions)."
)
RESEARCH_PROMPT  = (
    "Write a deep research report summarizing macro trends affecting this company's industry over the next 2 years. "
    "Include a table of the top 10 most important sources (Source Name | Why It Matters). Summarize key themes."
)
INTEL_PROMPT = (
    "Create a competitive intelligence cheat sheet: "
    "Top 3 Things to Know (bold headline, 3-4 evidence bullets, 'Your Angle' recommendation each), "
    "then 'Market Numbers to Drop in Conversation' with 7-10 stats with dollar signs and percentages."
)


async def main():
    os.makedirs(FOLDER, exist_ok=True)
    print(f"\n🚀 Meeting Prep Pipeline")
    print(f"   Company : {COMPANY}")
    print(f"   Output  : {FOLDER}\n")

    async with await NotebookLMClient.from_storage() as client:

        # ── Phase 1: Create Notebook ───────────────────────────────────────
        print("1. Creating notebook...")
        nb = await client.notebooks.create(f"Meeting Prep - {COMPANY}")
        print(f"   Notebook ID: {nb.id}")

        # ── Phase 1.2: Add seed data ───────────────────────────────────────
        print("2. Adding seed data...")
        await client.sources.add_text(nb.id, f"{COMPANY} - Company Profile", PROFILE)
        await asyncio.sleep(2)
        try:
            await client.sources.add_url(nb.id, f"https://{DOMAIN}")
        except Exception as e:
            print(f"   (URL source skipped: {e})")

        # ── Phase 2: Deep/Fast Research ────────────────────────────────────
        print(f"3. Starting {RESEARCH_MODE} research...")
        research = await client.research.start(
            nb.id,
            f"{COMPANY} {DOMAIN} competitors market UAE 2026",
            source="web",
            mode=RESEARCH_MODE,
        )
        task_id = research["task_id"]

        while True:
            status = await client.research.poll(nb.id)
            if status.get("status") == "completed":
                break
            print("   Polling research...")
            await asyncio.sleep(5)

        sources = status.get("sources", [])
        print(f"   Found {len(sources)} sources")

        # Batch import (max 20 per call to avoid timeout)
        for i in range(0, len(sources), 20):
            batch = sources[i : i + 20]
            await client.research.import_sources(nb.id, task_id, batch)
            print(f"   Imported {i + len(batch)}/{len(sources)} sources")
            await asyncio.sleep(3)

        # ── Phase 3: Generate Markdown Content ────────────────────────────
        print("4. Generating briefing documents...")
        for filename, prompt in [
            ("01_briefing_doc.md",       BRIEFING_PROMPT),
            ("02_deep_research_report.md", RESEARCH_PROMPT),
            ("03_competitive_intel.md",  INTEL_PROMPT),
        ]:
            res = await client.chat.ask(nb.id, prompt)
            Path(FOLDER, filename).write_text(res.answer, encoding="utf-8")
            print(f"   ✓ {filename}")
            await asyncio.sleep(2)

        # ── Phase 3.6-3.7: Quiz & Flashcards ─────────────────────────────
        print("5. Generating studio artifacts (quiz, flashcards, audio)...")
        try:
            gen_audio  = await client.artifacts.generate_audio(nb.id)
            gen_quiz   = await client.artifacts.generate_quiz(nb.id)
            gen_cards  = await client.artifacts.generate_flashcards(nb.id)
        except Exception as e:
            print(f"   Error starting generation: {e}")
            gen_audio = gen_quiz = gen_cards = None

        async def wait_and_download(gen, label, download_fn, path):
            if gen is None:
                return
            try:
                print(f"   Waiting for {label}...")
                await client.artifacts.wait_for_completion(nb.id, gen.task_id, timeout=300)
                await download_fn(nb.id, path)
                print(f"   ✓ {label} → {Path(path).name}")
            except TimeoutError:
                print(f"   ⚠ {label} timed out — may still be generating in NotebookLM")
            except Exception as e:
                print(f"   ⚠ {label} download failed: {e}")

        await wait_and_download(gen_quiz,   "quiz",       client.artifacts.download_quiz,
                                os.path.join(FOLDER, "06_pre_call_quiz.md"))
        # Pass output_format for quiz/flashcards
        if gen_quiz:
            try:
                await client.artifacts.wait_for_completion(nb.id, gen_quiz.task_id, timeout=5)
            except Exception:
                pass
            try:
                await client.artifacts.download_quiz(nb.id, os.path.join(FOLDER, "06_pre_call_quiz.md"), output_format="markdown")
                print(f"   ✓ quiz (markdown)")
            except Exception as e:
                print(f"   ⚠ quiz: {e}")

        if gen_cards:
            try:
                await client.artifacts.wait_for_completion(nb.id, gen_cards.task_id, timeout=300)
            except TimeoutError:
                pass
            try:
                await client.artifacts.download_flashcards(nb.id, os.path.join(FOLDER, "07_flashcards.md"), output_format="markdown")
                print(f"   ✓ flashcards (markdown)")
            except Exception as e:
                print(f"   ⚠ flashcards: {e}")

        if gen_audio:
            try:
                await client.artifacts.wait_for_completion(nb.id, gen_audio.task_id, timeout=300)
            except TimeoutError:
                pass
            try:
                await client.artifacts.download_audio(nb.id, os.path.join(FOLDER, "audio_briefing.mp3"))
                print(f"   ✓ audio_briefing.mp3")
            except Exception as e:
                print(f"   ⚠ audio: {e}")

        # ── Phase 4: INDEX ─────────────────────────────────────────────────
        idx = f"""# Meeting Prep Package: {COMPANY}
**Generated:** {__import__('datetime').date.today()}
**Meeting Context:** {CONTEXT}

## Files
| # | File | Description |
|---|------|-------------|
| 1 | 01_briefing_doc.md | Executive pre-meeting briefing |
| 2 | 02_deep_research_report.md | Deep research summary |
| 3 | 03_competitive_intel.md | Competitive intelligence |
| 4 | 06_pre_call_quiz.md | Knowledge quiz |
| 5 | 07_flashcards.md | Flashcards |
| 6 | audio_briefing.mp3 | AI podcast briefing |
| 7 | index.html | Interactive dashboard |

## Cloud
- **NotebookLM Notebook:** {nb.id}

## View Dashboard
```bash
cd "{FOLDER}"
python3 -m http.server 8888
# Open http://localhost:8888
```
"""
        Path(FOLDER, "00_INDEX.md").write_text(idx, encoding="utf-8")

        # ── Phase 5: HTML Dashboard ────────────────────────────────────────
        print("6. Building HTML dashboard...")
        _build_dashboard(COMPANY, FOLDER)
        print(f"   ✓ index.html")

        print(f"\n✅ Done! Open your dashboard:")
        print(f"   cd \"{FOLDER}\"")
        print(f"   python3 -m http.server 8888")
        print(f"   # Then visit http://localhost:8888\n")


def _build_dashboard(company: str, folder: str) -> None:
    """Write the premium glassmorphic HTML dashboard."""
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Meeting Prep — {company} | Antigravity OS</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.0/css/all.min.css">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box;}}
body{{font-family:'Inter',sans-serif;background:#06060a;color:#e2e8f0;min-height:100vh;overflow:hidden;}}
body::before{{content:'';position:fixed;inset:0;background:radial-gradient(ellipse 80% 60% at 10% 20%,rgba(59,130,246,.12),transparent),radial-gradient(ellipse 60% 50% at 90% 80%,rgba(168,85,247,.10),transparent);pointer-events:none;z-index:0;}}
.glass{{background:rgba(15,23,42,.55);backdrop-filter:blur(16px);border:1px solid rgba(255,255,255,.06);}}
.glass-strong{{background:rgba(15,23,42,.75);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,.08);}}
::-webkit-scrollbar{{width:6px;}} ::-webkit-scrollbar-thumb{{background:rgba(100,116,139,.3);border-radius:3px;}}
.md h1{{font-size:1.75rem;font-weight:800;margin-bottom:1rem;color:#f8fafc;}}
.md h2{{font-size:1.35rem;font-weight:700;margin:2rem 0 .75rem;color:#e2e8f0;border-bottom:1px solid rgba(255,255,255,.06);padding-bottom:.5rem;}}
.md h3{{font-size:1.1rem;font-weight:600;margin:1.5rem 0 .5rem;color:#cbd5e1;}}
.md p{{margin-bottom:.85rem;line-height:1.75;color:#94a3b8;font-size:.925rem;}}
.md ul{{list-style:none;padding-left:0;margin-bottom:1rem;}}
.md ul li{{position:relative;padding-left:1.25rem;margin-bottom:.35rem;color:#94a3b8;font-size:.925rem;}}
.md ul li::before{{content:'▸';position:absolute;left:0;color:#3b82f6;font-size:.75rem;top:3px;}}
.md strong{{color:#f1f5f9;font-weight:600;}}
.md table{{width:100%;border-collapse:collapse;margin:1.5rem 0;border-radius:12px;overflow:hidden;font-size:.875rem;}}
.md th{{background:rgba(59,130,246,.12);padding:.75rem 1rem;text-align:left;color:#93c5fd;font-weight:600;border-bottom:1px solid rgba(59,130,246,.15);}}
.md td{{padding:.75rem 1rem;border-bottom:1px solid rgba(255,255,255,.04);color:#94a3b8;vertical-align:top;}}
.sidebar-btn{{transition:all .2s;border-left:3px solid transparent;}}
.sidebar-btn:hover{{background:rgba(255,255,255,.04);}}
.sidebar-btn.active{{background:linear-gradient(90deg,rgba(59,130,246,.12),transparent);border-left-color:#3b82f6;color:#fff;}}
.viz-bar{{display:inline-block;width:3px;border-radius:2px;background:linear-gradient(to top,#3b82f6,#a78bfa);animation:vizPulse .8s ease-in-out infinite alternate;}}
@keyframes vizPulse{{0%{{height:4px;}}100%{{height:20px;}}}}
.viz-bar:nth-child(1){{animation-delay:0s;}} .viz-bar:nth-child(2){{animation-delay:.15s;}} .viz-bar:nth-child(3){{animation-delay:.3s;}}
.viz-bar:nth-child(4){{animation-delay:.1s;}} .viz-bar:nth-child(5){{animation-delay:.4s;}} .viz-bar:nth-child(6){{animation-delay:.2s;}}
.card-scene{{perspective:800px;}}
.card-inner{{position:relative;width:100%;height:300px;transform-style:preserve-3d;transition:transform .6s cubic-bezier(.4,.2,.2,1);}}
.card-inner.flipped{{transform:rotateY(180deg);}}
.card-face{{position:absolute;inset:0;backface-visibility:hidden;border-radius:16px;display:flex;align-items:center;justify-content:center;padding:2rem;text-align:center;font-size:1.05rem;line-height:1.6;}}
.card-front{{background:linear-gradient(135deg,#1e1b4b,#312e81,#4c1d95);border:1px solid rgba(139,92,246,.25);color:#e0e7ff;}}
.card-back{{background:linear-gradient(135deg,#78350f,#92400e,#a16207);border:1px solid rgba(251,191,36,.3);color:#fef3c7;transform:rotateY(180deg);}}
.quiz-option{{transition:all .2s;cursor:pointer;border:1px solid rgba(255,255,255,.08);}}
.quiz-option:hover:not(.answered){{border-color:rgba(59,130,246,.4);background:rgba(59,130,246,.08);}}
.quiz-option.correct{{border-color:rgba(34,197,94,.5)!important;background:rgba(34,197,94,.1)!important;}}
.quiz-option.wrong{{border-color:rgba(239,68,68,.5)!important;background:rgba(239,68,68,.1)!important;}}
.tab-panel{{animation:fadeSlide .35s ease;}}
@keyframes fadeSlide{{from{{opacity:0;transform:translateY(8px);}}to{{opacity:1;transform:translateY(0);}}}}
.dot{{transition:all .3s;}} .dot.active{{background:#a78bfa;transform:scale(1.4);}}
</style>
</head>
<body class="flex flex-col h-screen">
<nav class="glass-strong flex items-center justify-between px-6 py-3 z-50 relative border-b border-white/5" style="flex-shrink:0;">
  <div class="flex items-center gap-3">
    <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-lg shadow-blue-500/20"><i class="fa-solid fa-rocket text-white text-xs"></i></div>
    <span class="font-extrabold text-sm tracking-[0.2em] uppercase bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-purple-400 to-amber-300">Antigravity OS</span>
  </div>
  <div class="flex items-center gap-3">
    <span class="text-[11px] font-semibold px-3 py-1.5 rounded-full bg-blue-500/10 text-blue-300 border border-blue-500/20">{company}</span>
  </div>
</nav>
<div class="flex flex-1 overflow-hidden relative z-10">
  <aside class="glass w-60 flex-shrink-0 flex flex-col border-r border-white/5" style="min-width:240px;">
    <div class="px-5 pt-6 pb-4 border-b border-white/5">
      <div class="text-[10px] uppercase tracking-[0.2em] text-slate-500 font-bold mb-1.5">Meeting With</div>
      <div class="text-lg font-bold text-white">{company}</div>
    </div>
    <nav class="flex-1 py-3 space-y-0.5 overflow-y-auto">
      <button onclick="openTab('briefing',this)" class="sidebar-btn active w-full text-left px-5 py-2.5 text-[13px] text-slate-300 flex items-center gap-3"><i class="fa-solid fa-clipboard-list w-4 text-blue-400"></i> Executive Briefing</button>
      <button onclick="openTab('intel',this)" class="sidebar-btn w-full text-left px-5 py-2.5 text-[13px] text-slate-300 flex items-center gap-3"><i class="fa-solid fa-chess-knight w-4 text-purple-400"></i> Competitive Intel</button>
      <button onclick="openTab('research',this)" class="sidebar-btn w-full text-left px-5 py-2.5 text-[13px] text-slate-300 flex items-center gap-3"><i class="fa-solid fa-microscope w-4 text-cyan-400"></i> Deep Research</button>
      <button onclick="openTab('quiz',this)" class="sidebar-btn w-full text-left px-5 py-2.5 text-[13px] text-slate-300 flex items-center gap-3"><i class="fa-solid fa-brain w-4 text-emerald-400"></i> Knowledge Test</button>
      <button onclick="openTab('flashcards',this)" class="sidebar-btn w-full text-left px-5 py-2.5 text-[13px] text-slate-300 flex items-center gap-3"><i class="fa-solid fa-layer-group w-4 text-amber-400"></i> Flashcards</button>
    </nav>
    <div class="p-4 border-t border-white/5 bg-black/30">
      <div class="text-[10px] font-bold uppercase tracking-[0.15em] text-slate-500 mb-2"><i class="fa-solid fa-podcast mr-1"></i> AI Audio Briefing</div>
      <div class="glass rounded-xl p-3 flex items-center gap-3">
        <button onclick="toggleAudio()" class="w-9 h-9 rounded-full bg-gradient-to-br from-blue-600 to-purple-600 flex items-center justify-center text-white shadow-lg shadow-blue-600/30 hover:shadow-blue-600/50 transition flex-shrink-0" id="audio-btn"><i id="play-icon" class="fa-solid fa-play text-xs ml-0.5"></i></button>
        <div class="flex-1">
          <div class="flex items-end gap-[3px] h-5 hidden" id="visualizer"><span class="viz-bar"></span><span class="viz-bar"></span><span class="viz-bar"></span><span class="viz-bar"></span><span class="viz-bar"></span><span class="viz-bar"></span></div>
          <div class="text-[11px] text-slate-400" id="audio-label">Ready to play</div>
        </div>
      </div>
      <audio id="audio-el" src="audio_briefing.mp3" preload="none"></audio>
    </div>
  </aside>
  <main class="flex-1 overflow-y-auto p-8" id="main-content">
    <section id="tab-briefing" class="tab-panel"><div class="glass-strong rounded-2xl p-8 max-w-4xl mx-auto"><div class="flex items-center gap-3 mb-6"><div class="w-10 h-10 rounded-xl bg-blue-500/15 flex items-center justify-center"><i class="fa-solid fa-clipboard-list text-blue-400"></i></div><div><h1 class="text-xl font-bold text-white">Executive Briefing</h1><p class="text-xs text-slate-500">Pre-meeting intelligence package</p></div></div><div class="md" id="md-briefing">Loading...</div></div></section>
    <section id="tab-intel" class="tab-panel hidden"><div class="glass-strong rounded-2xl p-8 max-w-4xl mx-auto"><div class="flex items-center gap-3 mb-6"><div class="w-10 h-10 rounded-xl bg-purple-500/15 flex items-center justify-center"><i class="fa-solid fa-chess-knight text-purple-400"></i></div><div><h1 class="text-xl font-bold text-white">Competitive Intelligence</h1><p class="text-xs text-slate-500">Market positioning & key stats</p></div></div><div class="md" id="md-intel">Loading...</div></div></section>
    <section id="tab-research" class="tab-panel hidden"><div class="glass-strong rounded-2xl p-8 max-w-4xl mx-auto"><div class="flex items-center gap-3 mb-6"><div class="w-10 h-10 rounded-xl bg-cyan-500/15 flex items-center justify-center"><i class="fa-solid fa-microscope text-cyan-400"></i></div><div><h1 class="text-xl font-bold text-white">Deep Research Report</h1><p class="text-xs text-slate-500">Macro trends & source analysis</p></div></div><div class="md" id="md-research">Loading...</div></div></section>
    <section id="tab-quiz" class="tab-panel hidden"><div class="glass-strong rounded-2xl p-8 max-w-4xl mx-auto"><div class="flex items-center gap-3 mb-4"><div class="w-10 h-10 rounded-xl bg-emerald-500/15 flex items-center justify-center"><i class="fa-solid fa-brain text-emerald-400"></i></div><div><h1 class="text-xl font-bold text-white">Knowledge Test</h1><p class="text-xs text-slate-500">Test your meeting readiness</p></div></div><div class="flex items-center gap-2 mb-6"><span class="glass rounded-lg px-3 py-1.5 text-emerald-300 text-xs font-semibold" id="quiz-score">Score: 0 / 0</span><span class="glass rounded-lg px-3 py-1.5 text-slate-400 text-xs" id="quiz-progress">0 answered</span></div><div id="quiz-container"></div></div></section>
    <section id="tab-flashcards" class="tab-panel hidden"><div class="glass-strong rounded-2xl p-8 max-w-3xl mx-auto"><div class="flex items-center gap-3 mb-6"><div class="w-10 h-10 rounded-xl bg-amber-500/15 flex items-center justify-center"><i class="fa-solid fa-layer-group text-amber-400"></i></div><div><h1 class="text-xl font-bold text-white">Flashcards</h1><p class="text-xs text-slate-500">Click to flip · arrows to navigate</p></div></div><div class="text-center mb-6"><span class="text-sm font-semibold text-slate-300" id="fc-counter">Card 1 of ?</span></div><div class="card-scene max-w-lg mx-auto mb-6" onclick="flipCard()"><div class="card-inner" id="fc-inner"><div class="card-face card-front" id="fc-front">Loading...</div><div class="card-face card-back" id="fc-back">Loading...</div></div></div><div class="flex items-center justify-center gap-4 mb-4"><button onclick="fcNav(-1)" class="w-10 h-10 rounded-full glass flex items-center justify-center text-slate-300 hover:text-white transition"><i class="fa-solid fa-chevron-left text-sm"></i></button><div class="flex gap-1.5 flex-wrap justify-center max-w-xs" id="fc-dots"></div><button onclick="fcNav(1)" class="w-10 h-10 rounded-full glass flex items-center justify-center text-slate-300 hover:text-white transition"><i class="fa-solid fa-chevron-right text-sm"></i></button></div></div></section>
  </main>
</div>
<script>
function openTab(id,btn){{document.querySelectorAll('.tab-panel').forEach(el=>el.classList.add('hidden'));document.getElementById('tab-'+id).classList.remove('hidden');document.querySelectorAll('.sidebar-btn').forEach(el=>el.classList.remove('active'));if(btn)btn.classList.add('active');}}
const mdMap={{briefing:'01_briefing_doc.md',intel:'03_competitive_intel.md',research:'02_deep_research_report.md'}};
async function loadMarkdown(){{for(const[k,f]of Object.entries(mdMap)){{try{{const r=await fetch(f);if(r.ok)document.getElementById('md-'+k).innerHTML=marked.parse(await r.text());else document.getElementById('md-'+k).innerHTML='<p class="text-red-400">Run: python3 -m http.server 8888</p>'}}catch(e){{document.getElementById('md-'+k).innerHTML='<p class="text-yellow-400">Serve via HTTP: python3 -m http.server 8888</p>';}}}}}}
let playing=false;const audioEl=document.getElementById('audio-el');
function toggleAudio(){{if(playing){{audioEl.pause();document.getElementById('play-icon').className='fa-solid fa-play text-xs ml-0.5';document.getElementById('visualizer').classList.add('hidden');document.getElementById('audio-label').classList.remove('hidden');document.getElementById('audio-label').textContent='Paused';}}else{{audioEl.play().catch(()=>{{document.getElementById('audio-label').textContent='Audio not found';}});document.getElementById('play-icon').className='fa-solid fa-pause text-xs';document.getElementById('visualizer').classList.remove('hidden');document.getElementById('audio-label').classList.add('hidden');}}playing=!playing;}}
audioEl.addEventListener('ended',()=>{{playing=false;document.getElementById('play-icon').className='fa-solid fa-play text-xs ml-0.5';document.getElementById('visualizer').classList.add('hidden');document.getElementById('audio-label').classList.remove('hidden');document.getElementById('audio-label').textContent='Finished';}});
let quizData=[],quizAnswered=0,quizCorrect=0;
async function loadQuiz(){{try{{const r=await fetch('06_pre_call_quiz.md');if(!r.ok)return;const t=await r.text();const blocks=t.split(/^## Question \\d+/m).filter(b=>b.trim());quizData=blocks.map(block=>{{const lines=block.trim().split('\\n').filter(l=>l.trim());const question=lines[0]||'';const options=[];let correctIdx=-1;lines.forEach(line=>{{const m=line.match(/^- \\[(x| )\\] (.+)/);if(m){{if(m[1]==='x')correctIdx=options.length;options.push(m[2]);}}}});return{{question,options,correctIdx}};}}).filter(q=>q.options.length>0);renderQuiz();}}catch(e){{console.error(e);}}}}
function renderQuiz(){{const c=document.getElementById('quiz-container');c.innerHTML='';quizData.forEach((q,qi)=>{{const d=document.createElement('div');d.className='mb-8 glass rounded-xl p-6';d.innerHTML=`<p class="text-sm font-semibold text-slate-200 mb-4"><span class="text-blue-400 mr-2">Q${{qi+1}}.</span>${{q.question}}</p><div class="space-y-2" id="q-opts-${{qi}}">${{q.options.map((opt,oi)=>`<div class="quiz-option rounded-lg px-4 py-3 text-sm text-slate-300 flex items-center gap-3" onclick="answerQuiz(${{qi}},${{oi}})" id="q${{qi}}-o${{oi}}"><span class="w-6 h-6 rounded-full glass flex items-center justify-center text-xs font-bold text-slate-400 flex-shrink-0">${{String.fromCharCode(65+oi)}}</span><span>${{opt}}</span></div>`).join('')}}</div>`;c.appendChild(d);}});updateQuizUI();}}
function answerQuiz(qi,oi){{const opts=document.getElementById('q-opts-'+qi);if(opts.classList.contains('done'))return;opts.classList.add('done');quizAnswered++;const correct=quizData[qi].correctIdx;if(oi===correct)quizCorrect++;document.getElementById(`q${{qi}}-o${{oi}}`).classList.add(oi===correct?'correct':'wrong');if(oi!==correct)document.getElementById(`q${{qi}}-o${{correct}}`).classList.add('correct');opts.querySelectorAll('.quiz-option').forEach(el=>el.classList.add('answered'));updateQuizUI();}}
function updateQuizUI(){{document.getElementById('quiz-score').textContent=`Score: ${{quizCorrect}} / ${{quizAnswered}}`;document.getElementById('quiz-progress').textContent=`${{quizAnswered}} of ${{quizData.length}} answered`;}}
let fcCards=[],fcIdx=0;
async function loadFlashcards(){{try{{const r=await fetch('07_flashcards.md');if(!r.ok)return;const t=await r.text();const blocks=t.split(/^## Card \\d+/m).filter(b=>b.trim());fcCards=blocks.map(b=>{{const qm=b.match(/\\*\\*Q:\\*\\*\\s*(.+)/);const am=b.match(/\\*\\*A:\\*\\*\\s*(.+)/);return{{q:qm?qm[1].trim():'',a:am?am[1].trim():''}}}}).filter(c=>c.q&&c.a);renderFC();}}catch(e){{console.error(e);}}}}
function renderFC(){{if(!fcCards.length)return;const c=fcCards[fcIdx];document.getElementById('fc-front').innerHTML=`<div><div class="text-xs uppercase tracking-widest text-indigo-300/60 mb-3">Question</div><div>${{c.q}}</div></div>`;document.getElementById('fc-back').innerHTML=`<div><div class="text-xs uppercase tracking-widest text-amber-300/60 mb-3">Answer</div><div>${{c.a}}</div></div>`;document.getElementById('fc-counter').textContent=`Card ${{fcIdx+1}} of ${{fcCards.length}}`;document.getElementById('fc-inner').classList.remove('flipped');const el=document.getElementById('fc-dots');el.innerHTML='';const start=Math.max(0,fcIdx-10);const end=Math.min(fcCards.length,start+20);for(let i=start;i<end;i++){{const d=document.createElement('span');d.className=`dot w-2 h-2 rounded-full ${{i===fcIdx?'active bg-purple-400':'bg-slate-600'}}`;d.style.cursor='pointer';d.onclick=()=>{{fcIdx=i;renderFC();}};el.appendChild(d);}}}}
function flipCard(){{document.getElementById('fc-inner').classList.toggle('flipped');}}
function fcNav(dir){{fcIdx=(fcIdx+dir+fcCards.length)%fcCards.length;renderFC();}}
document.addEventListener('keydown',e=>{{if(e.key==='ArrowLeft')fcNav(-1);if(e.key==='ArrowRight')fcNav(1);if(e.key===' '&&!document.getElementById('tab-flashcards').classList.contains('hidden')){{e.preventDefault();flipCard();}}}});
loadMarkdown();loadQuiz();loadFlashcards();
</script>
</body></html>"""
    Path(folder, "index.html").write_text(html, encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
