import streamlit as st
import os
import json
import pandas as pd
from dotenv import load_dotenv
from agent.pipeline import run_pipeline

load_dotenv()

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Sentinel · AI Code Review",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Design system ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,400;12..96,600;12..96,800&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
    --blue:      #1d4ed8;
    --blue-deep: #0c2a7a;
    --blue-ink:  #0a1f4d;
    --yellow:    #ffd60a;
    --yellow-dk: #f5c400;
    --cream:     #faf6ec;
    --cream-2:   #f3ecd9;
    --ink:       #0a1f4d;
    --muted:     #5b6788;
    --line:      #e3d9bf;
}

.stApp {
    background:
        radial-gradient(circle at 12% 8%, #fffdf5 0%, transparent 45%),
        radial-gradient(circle at 88% 0%, #eef2ff 0%, transparent 40%),
        var(--cream);
    color: var(--ink);
}
html, body, [class*="css"] { font-family: 'Bricolage Grotesque', sans-serif; }
code, pre, .stCode, .mono { font-family: 'JetBrains Mono', monospace !important; }
.block-container { padding-top: 2.5rem; max-width: 1200px; }

.hero {
    border: 2.5px solid var(--ink);
    border-radius: 18px;
    background: var(--blue);
    padding: 2.2rem 2.4rem;
    position: relative;
    overflow: hidden;
    box-shadow: 10px 10px 0 var(--ink);
    margin-bottom: 2rem;
}
.hero::after {
    content: "◆";
    position: absolute;
    right: -10px; top: -30px;
    font-size: 11rem;
    color: var(--yellow);
    opacity: 0.18;
    transform: rotate(12deg);
}
.hero-kicker {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    letter-spacing: 0.32em;
    text-transform: uppercase;
    color: var(--yellow);
    margin-bottom: 0.4rem;
}
.hero-title {
    font-size: 3.4rem;
    font-weight: 800;
    line-height: 0.95;
    letter-spacing: -0.03em;
    color: #fff;
    margin: 0;
}
.hero-title .accent { color: var(--yellow); font-style: italic; }
.hero-sub {
    font-family: 'JetBrains Mono', monospace;
    color: #c7d2fe;
    font-size: 0.82rem;
    margin-top: 0.7rem;
    letter-spacing: 0.04em;
}

.pipe-row { display:flex; gap:0.5rem; margin-top:1.2rem; flex-wrap:wrap; }
.pipe-pill {
    background: rgba(255,255,255,0.12);
    border: 1px solid rgba(255,255,255,0.25);
    color: #fff;
    font-family:'JetBrains Mono',monospace;
    font-size: 0.68rem;
    letter-spacing: 0.1em;
    padding: 4px 12px;
    border-radius: 100px;
    text-transform: uppercase;
}
.pipe-pill b { color: var(--yellow); }

.sec-label {
    font-family:'JetBrains Mono',monospace;
    font-size:0.74rem;
    letter-spacing:0.28em;
    text-transform:uppercase;
    color:var(--blue);
    border-bottom:2px solid var(--ink);
    padding-bottom:0.4rem;
    margin: 1.6rem 0 1rem 0;
    display:inline-block;
}

.metric-tile {
    border: 2px solid var(--ink);
    border-radius: 12px;
    background: #fff;
    padding: 1.1rem 0.6rem;
    text-align: center;
    box-shadow: 4px 4px 0 var(--ink);
    transition: transform .15s;
}
.metric-tile:hover { transform: translate(-2px,-2px); box-shadow: 6px 6px 0 var(--ink); }
.metric-num { font-size: 2.3rem; font-weight: 800; line-height: 1; }
.metric-cap {
    font-family:'JetBrains Mono',monospace;
    font-size:0.66rem; letter-spacing:0.14em; text-transform:uppercase;
    color: var(--muted); margin-top: 0.35rem;
}

.stat-strip {
    font-family:'JetBrains Mono',monospace;
    font-size:0.8rem; color:var(--blue-ink);
    background: var(--yellow);
    border: 2px solid var(--ink);
    border-radius: 100px;
    padding: 0.5rem 1.2rem;
    display:inline-block;
    box-shadow: 3px 3px 0 var(--ink);
    margin-top: 0.4rem;
}

.card {
    border: 2px solid var(--ink);
    border-radius: 14px;
    background: #fff;
    padding: 1.2rem 1.4rem;
    margin-bottom: 0.9rem;
    box-shadow: 5px 5px 0 var(--ink);
    position: relative;
}
.card.lowconf {
    background: #fffdf0;
    border-style: dashed;
    box-shadow: 5px 5px 0 var(--yellow-dk);
}
.card-head { display:flex; align-items:center; gap:0.5rem; flex-wrap:wrap; margin-bottom:0.6rem; }
.card-title { font-size:1.12rem; font-weight:700; line-height:1.25; margin-bottom:0.3rem; }
.card-body { color:#26345e; font-size:0.92rem; line-height:1.6; }
.card-sug {
    color:var(--blue); font-size:0.86rem; margin-top:0.6rem;
    border-left:3px solid var(--yellow); padding-left:0.7rem;
}

.tag {
    font-family:'JetBrains Mono',monospace;
    font-size:0.66rem; font-weight:700; letter-spacing:0.08em;
    padding:3px 9px; border-radius:6px; text-transform:uppercase;
    border:1.5px solid var(--ink);
}
.tag-critical { background:#ffe1e1; color:#b00020; }
.tag-high     { background:#ffe9d6; color:#c2410c; }
.tag-medium   { background:var(--yellow); color:var(--ink); }
.tag-low      { background:#dcfce7; color:#15803d; }
.tag-info     { background:#dbeafe; color:var(--blue); }
.tag-cat { background:var(--cream-2); color:var(--blue-ink); }
.tag-file {
    margin-left:auto; background:var(--blue); color:#fff; border-color:var(--blue-ink);
    text-transform:none; letter-spacing:0;
}
.tag-verify { background:var(--ink); color:var(--yellow); }

.conf-wrap { margin-top:0.7rem; display:flex; align-items:center; gap:0.7rem; }
.conf-num { font-family:'JetBrains Mono',monospace; font-weight:700; font-size:0.78rem; min-width:48px; }
.conf-track { flex:1; height:9px; background:var(--cream-2); border:1.5px solid var(--ink); border-radius:100px; overflow:hidden; }
.conf-fill { height:100%; }

[data-testid="stSidebar"] { background: var(--blue-ink); border-right: 3px solid var(--ink); }
[data-testid="stSidebar"] * { color: #e8edff !important; }
[data-testid="stSidebar"] h3 {
    font-family:'JetBrains Mono',monospace !important;
    font-size:0.78rem !important; letter-spacing:0.2em; text-transform:uppercase;
    color: var(--yellow) !important;
}

.stTextInput input {
    background:#fff !important;
    border:2px solid var(--ink) !important;
    border-radius:10px !important;
    color:var(--ink) !important;
    font-family:'JetBrains Mono',monospace !important;
    font-size:0.95rem !important;
    box-shadow: 3px 3px 0 var(--ink);
}
[data-testid="stSidebar"] .stTextInput input {
    background:#13316b !important; color:#fff !important;
    border:2px solid #2a4a96 !important; box-shadow:none;
}

.stButton>button {
    background: var(--yellow);
    color: var(--ink);
    border: 2.5px solid var(--ink);
    border-radius: 10px;
    font-family:'JetBrains Mono',monospace;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 0.65rem 1.4rem;
    box-shadow: 4px 4px 0 var(--ink);
    transition: all .12s;
}
.stButton>button:hover { background: var(--yellow-dk); transform: translate(-2px,-2px); box-shadow: 6px 6px 0 var(--ink); }
.stButton>button:active { transform: translate(2px,2px); box-shadow: 1px 1px 0 var(--ink); }

.stDownloadButton>button {
    background:#fff; color:var(--blue-ink);
    border:2.5px solid var(--ink); border-radius:10px;
    font-family:'JetBrains Mono',monospace; font-weight:700;
    box-shadow: 4px 4px 0 var(--ink);
}
.stDownloadButton>button:hover { background:var(--blue); color:#fff; transform:translate(-2px,-2px); box-shadow:6px 6px 0 var(--ink); }

.stProgress > div > div > div { background: var(--blue) !important; }
.stProgress > div > div { background: var(--cream-2) !important; }

hr { border:none; border-top:2px dashed var(--line); }
[data-testid="stSidebar"] hr { border-top:1px solid #2a4a96; }
.stAlert { border-radius:10px; border:2px solid var(--ink); }
</style>
""", unsafe_allow_html=True)


st.markdown("""
<div class="hero">
    <div class="hero-kicker">◆ Agentic AI · AST-aware · Confidence-rated</div>
    <h1 class="hero-title">Sentinel <span class="accent">/ code review</span></h1>
    <div class="hero-sub">clone → parse → review → rate · powered by Gemini</div>
    <div class="pipe-row">
        <span class="pipe-pill"><b>01</b> Ingest</span>
        <span class="pipe-pill"><b>02</b> Parse AST</span>
        <span class="pipe-pill"><b>03</b> LLM Review</span>
        <span class="pipe-pill"><b>04</b> Confidence</span>
    </div>
</div>
""", unsafe_allow_html=True)


with st.sidebar:
    st.markdown("### Config")
    api_key = st.text_input(
        "Gemini API Key", type="password",
        value=os.getenv("GEMINI_API_KEY", ""),
        help="Free key -> aistudio.google.com",
    )
    st.markdown("---")
    st.markdown("### Filters")
    severity_filter = st.multiselect(
        "Severity",
        ["critical", "high", "medium", "low", "info"],
        default=["critical", "high", "medium", "low", "info"],
    )
    category_filter = st.multiselect(
        "Category",
        ["bug", "security", "performance", "style", "maintainability", "logic"],
        default=["bug", "security", "performance", "style", "maintainability", "logic"],
    )
    confidence_threshold = st.slider("Min confidence %", 0, 100, 0, 5)
    show_low_confidence = st.checkbox("Show 'verify this' section", value=True)
    st.markdown("---")
    st.markdown("### About")
    st.caption(
        "Clones a public GitHub repo, parses Python via AST, then asks Gemini "
        "for structured, confidence-rated review comments."
    )


c1, c2 = st.columns([3, 1])
with c1:
    repo_url = st.text_input(
        "repo", placeholder="https://github.com/username/repository",
        label_visibility="collapsed",
    )
with c2:
    run_btn = st.button("Analyze", use_container_width=True)


st.session_state.setdefault("results", None)
st.session_state.setdefault("repo_meta", None)


if run_btn:
    if not repo_url.strip():
        st.error("Enter a GitHub repository URL.")
    elif not api_key.strip():
        st.error("Enter your Gemini API key in the sidebar.")
    else:
        os.environ["GROQ_API_KEY"] = api_key.strip()
        bar = st.progress(0, text="Initializing...")
        status = st.empty()

        def update(step, total, msg):
            bar.progress(step / total, text=msg)
            status.info(msg)

        try:
            results, meta = run_pipeline(repo_url.strip(), progress_callback=update)
            st.session_state.results = results
            st.session_state.repo_meta = meta
            bar.progress(1.0, text="Done")
            status.success(f"Analyzed {meta['files_parsed']} files - {len(results)} comments.")
        except Exception as exc:
            bar.empty()
            status.error(f"Pipeline error: {exc}")
            st.exception(exc)


SEV_HEX = {"critical": "#b00020", "high": "#c2410c", "medium": "#f5c400",
           "low": "#15803d", "info": "#1d4ed8"}

def conf_hex(c):
    if c >= 80: return "#15803d"
    if c >= 60: return "#1d4ed8"
    return "#c2410c"

def render_card(r, low=False):
    sev   = r.get("severity", "info").lower()
    conf  = r.get("confidence", 50)
    cat   = r.get("category", "general")
    file_ = r.get("file", "unknown")
    loc   = r.get("location", "")
    verify = '<span class="tag tag-verify">verify this</span>' if low else ""
    st.markdown(f"""
    <div class="card {'lowconf' if low else ''}">
        <div class="card-head">
            {verify}
            <span class="tag tag-{sev}">{sev}</span>
            <span class="tag tag-cat">{cat}</span>
            <span class="tag tag-file">{file_}{(' . ' + loc) if loc else ''}</span>
        </div>
        <div class="card-title">{r.get('title','Review comment')}</div>
        <div class="card-body">{r.get('comment','')}</div>
        {('<div class="card-sug">-> ' + r['suggestion'] + '</div>') if r.get('suggestion') else ''}
        <div class="conf-wrap">
            <span class="conf-num" style="color:{conf_hex(conf)};">{conf}%</span>
            <span class="conf-track"><span class="conf-fill" style="width:{conf}%;background:{conf_hex(conf)};"></span></span>
        </div>
    </div>
    """, unsafe_allow_html=True)


if st.session_state.results is not None:
    results = st.session_state.results
    meta = st.session_state.repo_meta

    st.markdown('<div class="sec-label">Summary</div>', unsafe_allow_html=True)
    counts = {s: 0 for s in ["critical", "high", "medium", "low", "info"]}
    for r in results:
        k = r.get("severity", "info").lower()
        counts[k] = counts.get(k, 0) + 1
    cols = st.columns(5)
    for col, (sev, n) in zip(cols, counts.items()):
        col.markdown(f"""
        <div class="metric-tile">
            <div class="metric-num" style="color:{SEV_HEX[sev]};">{n}</div>
            <div class="metric-cap">{sev}</div>
        </div>""", unsafe_allow_html=True)

    avg = sum(r.get("confidence", 50) for r in results) / len(results) if results else 0
    st.markdown(
        f'<div class="stat-strip">{meta.get("files_parsed",0)} files &nbsp;.&nbsp; '
        f'{meta.get("functions_found",0)} functions &nbsp;.&nbsp; '
        f'{meta.get("classes_found",0)} classes &nbsp;.&nbsp; '
        f'{avg:.0f}% avg confidence</div>',
        unsafe_allow_html=True,
    )

    filtered = [
        r for r in results
        if r.get("severity", "info").lower() in severity_filter
        and r.get("category", "").lower() in category_filter
        and r.get("confidence", 50) >= confidence_threshold
    ]
    high_conf = [r for r in filtered if r.get("confidence", 50) >= 60]
    low_conf  = [r for r in filtered if r.get("confidence", 50) < 60]

    st.markdown(f'<div class="sec-label">Review Comments . {len(high_conf)}</div>', unsafe_allow_html=True)
    if high_conf:
        for r in high_conf:
            render_card(r, low=False)
    else:
        st.info("No comments match the current filters.")

    if show_low_confidence and low_conf:
        st.markdown(f'<div class="sec-label">Verify These . Low Confidence . {len(low_conf)}</div>', unsafe_allow_html=True)
        st.caption("Confidence below 60% - review manually before acting.")
        for r in low_conf:
            render_card(r, low=True)

    st.markdown('<div class="sec-label">Export</div>', unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        st.download_button("Download JSON", json.dumps(filtered, indent=2),
                           "review_comments.json", "application/json",
                           use_container_width=True)
    with d2:
        if filtered:
            df = pd.DataFrame(filtered)[["file", "severity", "category", "confidence", "title", "comment"]]
            st.download_button("Download CSV", df.to_csv(index=False),
                               "review_comments.csv", "text/csv",
                               use_container_width=True)
else:
    st.markdown("""
    <div style="text-align:center; padding:3.5rem 2rem;">
        <div style="font-size:3.5rem; color:#1d4ed8;">◆</div>
        <h2 style="font-weight:800; letter-spacing:-0.02em; margin:0.3rem 0;">Point it at a repo</h2>
        <p style="font-family:'JetBrains Mono',monospace; color:#5b6788; font-size:0.85rem;">
            Paste a public GitHub URL above and hit <b>Analyze</b>.<br>
            The agent clones, parses, and reviews - every comment self-rated for confidence.
        </p>
    </div>
    """, unsafe_allow_html=True)
