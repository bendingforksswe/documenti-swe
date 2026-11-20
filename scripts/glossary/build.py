#!/usr/bin/env python3
import argparse
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent
REPO_ROOT = ROOT.parent.parent
SOURCE = ROOT / "glossary.json"
HTML_OUT = ROOT / "glossario.html"
TEX_OUT = REPO_ROOT / "rtb" / "glossario.tex"
PDF_OUT = TEX_OUT.with_suffix(".pdf")
SITE_CSS = "assets/css/style.css"
FAVICON = "assets/img/favicon.png"
TYPES = ("term", "abbr")
ALLOWED_FIELDS = {"term", "type", "expansion", "definition"}
AUX_EXTENSIONS = (".aux", ".toc", ".out", ".log", ".fls", ".fdb_latexmk", ".synctex.gz")

TEX_MAP = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
    "\u2192": r"$\rightarrow$",
    "\u2190": r"$\leftarrow$",
}
TEX_PATTERN = re.compile("|".join(re.escape(k) for k in TEX_MAP))


def sort_key(text):
    decomposed = unicodedata.normalize("NFD", text)
    plain = "".join(c for c in decomposed if not unicodedata.combining(c))
    return plain.casefold()


def slugify(text):
    plain = sort_key(text)
    slug = re.sub(r"[^a-z0-9]+", "-", plain).strip("-")
    return slug or "term"


def group_letter(term):
    for c in sort_key(term):
        if c.isalnum():
            return c.upper() if c.isalpha() else "#"
    return "#"


def tex_escape(text):
    return TEX_PATTERN.sub(lambda m: TEX_MAP[m.group()], text)


def load():
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    return data.get("meta", {}), data.get("changelog", []), data["entries"]


def validate(entries):
    errors, known = [], {}
    for i, e in enumerate(entries, 1):
        term = e.get("term")
        if not term:
            errors.append(f"voce {i}: campo 'term' mancante")
            continue
        extra = set(e.keys()) - ALLOWED_FIELDS
        if extra:
            errors.append(f"{term}: campi non ammessi ({', '.join(sorted(extra))})")
        key = sort_key(term)
        if key in known:
            errors.append(f"termine duplicato: {term}")
        known[key] = term
        if e.get("type") not in TYPES:
            errors.append(f"{term}: 'type' deve essere uno tra {', '.join(TYPES)}")
        if not e.get("definition"):
            errors.append(f"{term}: campo 'definition' mancante")
        if e.get("type") == "abbr" and not e.get("expansion"):
            errors.append(f"{term}: campo 'expansion' mancante")
    return errors


def save_sorted_json(meta, changelog, entries):
    cleaned_entries = [
        {k: e[k] for k in ("term", "type", "expansion", "definition") if k in e}
        for e in entries
    ]
    payload = {
        "meta": meta,
        "changelog": changelog,
        "entries": cleaned_entries,
    }
    formatted = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if SOURCE.read_text(encoding="utf-8") != formatted:
        SOURCE.write_text(formatted, encoding="utf-8", newline="\n")


def build_link_matcher(entries):
    # Mappa sia il termine (es. "POC") sia l'espansione (es. "Proof of Concept") allo slug del termine
    alias_to_slug = {}
    alias_to_owner = {}
    for e in entries:
        owner = e["term"]
        slug = slugify(owner)
        alias_to_slug[owner.casefold()] = slug
        alias_to_owner[owner.casefold()] = owner
        if e.get("expansion"):
            exp = e["expansion"].strip()
            if exp and exp.casefold() not in alias_to_slug:
                alias_to_slug[exp.casefold()] = slug
                alias_to_owner[exp.casefold()] = owner

    # Ordina dal più lungo al più corto per evitare match parziali
    aliases = sorted(alias_to_slug.keys(), key=len, reverse=True)
    if not aliases:
        return None, alias_to_slug, alias_to_owner
    pattern = re.compile(
        r"(?<![A-Za-zÀ-ÖØ-öø-ÿ0-9_-])("
        + "|".join(re.escape(a) for a in aliases)
        + r")(?![A-Za-zÀ-ÖØ-öø-ÿ0-9_-])",
        re.IGNORECASE,
    )
    return pattern, alias_to_slug, alias_to_owner


def linkify_tex(definition, current_term, pattern, alias_to_slug, alias_to_owner):
    if not pattern:
        return tex_escape(definition)
    out = []
    last = 0
    for m in pattern.finditer(definition):
        matched = m.group(0)
        key = matched.casefold()
        owner = alias_to_owner.get(key)
        if owner == current_term:
            continue
        out.append(tex_escape(definition[last : m.start()]))
        slug = alias_to_slug[key]
        out.append(rf"\hyperlink{{term-{slug}}}{{\emph{{{tex_escape(matched)}}}}}")
        last = m.end()
    out.append(tex_escape(definition[last:]))
    return "".join(out)


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Glossario · @@PROJECT@@ · @@GROUP@@</title>
<link rel="icon" href="@@FAVICON@@">
<style>:root{--sfondo:#f5f7fe;--superficie:#fff;--testo:#0c1230;--testo-2:#4a5275;--linea:#e1e6f5;--accento:#2551d6;--bottone:#2551d6;--bottone-testo:#fff;--chip:#e8eeff;--prep-sfondo:#eef0fa;--prep-testo:#4a5275;--titoli:system-ui,sans-serif;--mono:ui-monospace,Consolas,monospace}</style>
<link rel="stylesheet" href="@@SITE_CSS@@">
<style>
[hidden]{display:none!important}
.pagina{display:flex;flex-direction:column;gap:24px}
.toolbar{position:sticky;top:var(--alt-testata,76px);z-index:5;background:var(--sfondo);padding:12px 0;display:flex;flex-direction:column;gap:12px;border-bottom:1px solid var(--linea)}
.search-row{display:flex;flex-wrap:wrap;gap:12px}
.search-box{flex:1 1 260px}
.search-box input{width:100%;padding:11px 16px;border:1px solid var(--linea);border-radius:12px;background:var(--superficie);color:var(--testo);font:inherit}
.search-box input:focus-visible{outline:3px solid var(--accento);outline-offset:2px}
.filters,.letters{display:flex;flex-wrap:wrap;gap:6px}
.chip{padding:9px 16px;border-radius:999px;border:1px solid var(--linea);background:var(--superficie);color:var(--testo-2);font:inherit;font-size:15px;font-weight:500;cursor:pointer;transition:background .15s,color .15s}
.chip:hover:not(.active):not(:disabled){background:var(--chip);color:var(--testo)}
.chip.active{background:var(--bottone);border-color:var(--bottone);color:var(--bottone-testo)}
.chip:disabled{opacity:.35;cursor:default}
.letters .chip{padding:5px 10px;font-family:var(--mono);font-size:13px}
.group{margin-bottom:40px}
.letter{margin:0 0 16px;font-family:var(--titoli);font-size:30px;line-height:1;color:var(--accento);scroll-margin-top:calc(var(--alt-testata,76px) + 190px)}
.entries{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--superficie);border:1px solid var(--linea);border-radius:20px;padding:24px;display:flex;flex-direction:column;gap:10px;scroll-margin-top:calc(var(--alt-testata,76px) + 190px);transition:box-shadow .3s,border-color .3s}
.card.highlight{border-color:var(--accento);box-shadow:0 0 0 3px var(--chip)}
.card-header{display:flex;flex-wrap:wrap;align-items:center;gap:8px 12px}
.card h3{margin:0;font-family:var(--titoli);font-size:21px;font-weight:600;letter-spacing:0;text-transform:none;color:var(--testo)}
.card p{margin:0}
.card .def{color:var(--testo)}
.gloss-link{color:var(--accento);text-decoration:underline;text-decoration-style:dotted;text-underline-offset:3px;font-weight:500}
.gloss-link:hover{text-decoration-style:solid}
@media (max-width:760px){
  .entries{grid-template-columns:1fr}
  .letters{flex-wrap:nowrap;overflow-x:auto;scrollbar-width:none}
  .letters::-webkit-scrollbar{display:none}
  .letter,.card{scroll-margin-top:calc(var(--alt-testata,76px) + 210px)}
}
</style>
</head>
<body>
<header class="header"><div class="contenitore testata-riga">
  <a class="brand" href="index.html"><img src="@@FAVICON@@" alt="">BENDING FORKS</a>
  <nav class="nav-links"><a href="index.html">← Torna al sito</a></nav>
  <div class="actions">
    <a href="Glossario.pdf">Scarica PDF</a>
    <button id="themeBtn" type="button" aria-label="Cambia tema">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>
    </button>
  </div>
</div></header>

<main class="contenitore"><div class="pagina">
  <div>
    <h2>Glossario</h2>
    <span id="totalCount"></span>
  </div>
  <div class="toolbar">
    <div class="search-row">
      <div class="search-box"><input type="search" id="searchInput" placeholder="Cerca un termine..." autocomplete="off" aria-label="Cerca un termine"></div>
      <div class="filters" id="filters">
        <button class="chip active" data-f="all">Tutti</button>
        <button class="chip" data-f="term">Termini</button>
        <button class="chip" data-f="abbr">Acronimi</button>
      </div>
    </div>
    <div class="letters" id="letterNav"></div>
  </div>
  <div id="lista"></div>
  <div class="empty" id="noResults" hidden>Nessun termine trovato</div>
</div></main>

<footer class="footer"><div class="contenitore piede-riga">
  <div>
    <strong>@@PROJECT@@ · @@GROUP@@</strong><br>
    <span>@@COURSE@@</span><br>
    <span>Versione @@VERSION@@</span>
  </div>
  <div>
    <a href="index.html">Sito del progetto</a> ·
    <a href="Glossario.pdf">PDF</a>
  </div>
</div></footer>

<script>
const DATA = @@DATA@@;
const $ = id => document.getElementById(id);
const norm = s => s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
const slugify = s => norm(s).replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'term';
let filter = 'all';

const ALIAS_MAP = new Map();
DATA.forEach(e => {
  const slug = slugify(e.term);
  ALIAS_MAP.set(e.term.toLowerCase(), { slug, owner: e.term });
  if (e.expansion) {
    const exp = e.expansion.trim().toLowerCase();
    if (exp && !ALIAS_MAP.has(exp)) ALIAS_MAP.set(exp, { slug, owner: e.term });
  }
});
const SORTED_ALIASES = Array.from(ALIAS_MAP.keys()).sort((a, b) => b.length - a.length);
const ESC_RE = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const LINK_RE = SORTED_ALIASES.length
  ? new RegExp('(^|[^A-Za-zÀ-ÖØ-öø-ÿ0-9_-])(' + SORTED_ALIASES.map(ESC_RE).join('|') + ')(?=$|[^A-Za-zÀ-ÖØ-öø-ÿ0-9_-])', 'gi')
  : null;

function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}

function jumpToTerm(slug) {
  let target = $('term-' + slug);
  if (!target) {
    filter = 'all';
    $('searchInput').value = '';
    document.querySelectorAll('#filters .chip').forEach(x => x.classList.toggle('active', x.dataset.f === 'all'));
    render();
    target = $('term-' + slug);
  }
  if (target) {
    const header = document.querySelector('.header');
    const toolbar = document.querySelector('.toolbar');
    const offset = (header ? header.offsetHeight : 0) + (toolbar ? toolbar.offsetHeight : 0) + 32;
    const top = target.getBoundingClientRect().top + window.scrollY - offset;
    window.scrollTo({ top: Math.max(0, top), behavior: 'smooth' });

    target.classList.remove('highlight');
    void target.offsetWidth;
    target.classList.add('highlight');
    setTimeout(() => target.classList.remove('highlight'), 2000);
  }
}

function buildLinkedDef(text, currentTerm) {
  const p = el('p', null, 'def');
  if (!LINK_RE) { p.textContent = text; return p; }
  LINK_RE.lastIndex = 0;
  let last = 0, m;
  while ((m = LINK_RE.exec(text)) !== null) {
    const prefix = m[1];
    const matched = m[2];
    const info = ALIAS_MAP.get(matched.toLowerCase());
    if (!info || info.owner === currentTerm) continue;
    const start = m.index + prefix.length;
    if (start > last) p.appendChild(document.createTextNode(text.slice(last, start)));
    const a = el('a', matched, 'gloss-link');
    a.href = '#term-' + info.slug;
    a.onclick = ev => { ev.preventDefault(); jumpToTerm(info.slug); };
    p.appendChild(a);
    last = start + matched.length;
  }
  if (last < text.length) p.appendChild(document.createTextNode(text.slice(last)));
  return p;
}

function render() {
  const q = norm($('searchInput').value.trim());
  const shown = DATA.filter(e =>
    (filter === 'all' || e.type === filter) &&
    (!q || norm(e.term + ' ' + (e.expansion || '') + ' ' + e.definition).includes(q)));
  const lista = $('lista');
  lista.replaceChildren();
  const present = new Set();
  let grid = null;
  let current = '';
  shown.forEach(e => {
    const L = norm(e.term)[0].toUpperCase();
    present.add(L);
    if (L !== current) {
      current = L;
      const g = el('div', null, 'group');
      const h = el('h2', L, 'letter'); h.id = 'letter-' + L;
      grid = el('div', null, 'entries');
      g.append(h, grid);
      lista.appendChild(g);
    }
    const a = el('article', null, 'card');
    a.id = 'term-' + slugify(e.term);
    const header = el('div', null, 'card-header');
    header.appendChild(el('h3', e.term));
    if (e.type === 'abbr') header.appendChild(el('span', 'Acronimo', 'badge prep'));
    a.appendChild(header);
    if (e.expansion) a.appendChild(el('p', e.expansion, 'meta'));
    a.appendChild(buildLinkedDef(e.definition, e.term));
    grid.appendChild(a);
  });
  $('noResults').hidden = shown.length > 0;
  $('totalCount').textContent = shown.length + (shown.length === 1 ? ' termine' : ' termini');
  const nav = $('letterNav');
  nav.replaceChildren();
  for (let c = 65; c <= 90; c++) {
    const L = String.fromCharCode(c);
    const b = el('button', L, 'chip');
    b.disabled = !present.has(L);
    b.onclick = () => {
      const target = $('letter-' + L);
      if (target) target.scrollIntoView();
    };
    nav.appendChild(b);
  }
}

$('searchInput').addEventListener('input', render);
document.querySelectorAll('#filters .chip').forEach(b => b.onclick = () => {
  filter = b.dataset.f;
  document.querySelectorAll('#filters .chip').forEach(x => x.classList.toggle('active', x === b));
  render();
});

const root = document.documentElement;
try { const s = localStorage.getItem('tema'); if (s) root.dataset.theme = s; } catch (e) {}
$('themeBtn').onclick = () => {
  const dark = root.dataset.theme ? root.dataset.theme === 'dark'
                                  : matchMedia('(prefers-color-scheme: dark)').matches;
  const next = dark ? 'light' : 'dark';
  root.dataset.theme = next;
  try { localStorage.setItem('tema', next); } catch (e) {}
};
render();
</script>
</body>
</html>
"""

TEX_TEMPLATE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[italian]{babel}
\usepackage{amsmath}
\usepackage{libertinus}
\usepackage[a4paper,top=25mm,bottom=25mm,left=22mm,right=22mm,headheight=15pt]{geometry}
\usepackage{graphicx}
\graphicspath{{./}{../}{../../}{../../../}{assets/}{Assets/}{assets/img/}{../assets/}{../Assets/}{../assets/img/}{../../assets/}{../../Assets/}{../../assets/img/}{../../../assets/}{../../../Assets/}{../../../assets/img/}}
\usepackage[table]{xcolor}
\usepackage{tabularx,array}
\usepackage{titlesec}
\usepackage{titletoc}
\usepackage{microtype}
\usepackage{fancyhdr}
\usepackage{enumitem}
\usepackage[hidelinks]{hyperref}

% Dati generali del documento
\newcommand{\docname}{Glossario}
\newcommand{\docversion}{@@VERSION@@}
\newcommand{\docdate}{@@DATE@@}

\newcommand{\ph}[1]{\textcolor{red}{[#1]}}

% Palette colori del gruppo Bending Forks
\definecolor{bfblue}{HTML}{1B3F9E}
\definecolor{bfrow}{HTML}{F2F5FC}
\definecolor{bfline}{HTML}{C9D1E6}
\definecolor{bfhead}{HTML}{2E6BE6}

\newcommand{\tightlist}{\setlength{\itemsep}{1pt}\setlength{\parskip}{0pt}}
\setlist{topsep=2pt}
\setlist[itemize]{leftmargin=1.3em,label=\textbullet}
\setlist[enumerate]{leftmargin=1.6em}
\setlength{\parindent}{0pt}
\sloppy
\setlength{\parskip}{5pt}
\renewcommand{\arraystretch}{1.45}
\setcounter{secnumdepth}{3}
\setcounter{tocdepth}{2}

% Formattazione titoli sezioni
\titleformat{\section}{\LARGE\bfseries\color{bfblue}}{}{0pt}{}[{\color{bfblue}\vspace{-2pt}\titlerule[0.9pt]}]
\titlespacing*{\section}{0pt}{14pt}{6pt}

% Sezioni per lettere del glossario senza numerazione (rimossa la linea duplicata)
\newcommand{\glossarysection}[1]{%
  \section{#1}%
  \vspace{4pt}%
}

% Formattazione singolo termine del glossario
\newcommand{\glossterm}[2]{%
  \textbf{\large#1}\par%
  \ifx&#2&%
  \else%
    #2\par%
  \fi%
  \vspace{8pt}%
}

% Indice con puntini/trattini
\contentsmargin{2.2em}
\newcommand{\bfleader}{\titlerule*[0.32em]{\textendash}}
\titlecontents{section}[0pt]{\addvspace{4pt}\large\bfseries}{}{}{\hspace{0.4em}\bfleader\contentspage}

% Intestazioni e piè di pagina
\pagestyle{fancy}
\fancyhf{}
\fancyhead[L]{\footnotesize\sffamily\bfseries\color{bfhead}\textls[120]{BENDING FORKS}}
\fancyhead[R]{\footnotesize\sffamily \normalsize Glossario}
\fancyfoot[C]{\small Pagina \thepage}
\renewcommand{\headrulewidth}{0.9pt}

% Colorazione alternata per le tabelle
\newcommand{\bftable}{\rowcolors{2}{bfrow}{white}}
\usepackage{etoolbox}
\AtBeginEnvironment{tabularx}{\bftable}

\begin{document}

% ---------- Copertina ----------
\begin{titlepage}
\centering
\vspace*{4mm}
\IfFileExists{logo-bending-forks-trasparente.png}{%
  \includegraphics[width=105mm]{logo-bending-forks-trasparente.png}\\[4mm]%
}{%
  \vspace*{10mm}{\Huge\bfseries\color{bfblue} BENDING FORKS}\\[10mm]%
}
\underline{bending.forks.swe@gmail.com}

\vspace{32mm}
{\fontsize{24}{28}\selectfont\bfseries Glossario\par}
\vspace{4mm}
{\large\color{bfblue}\textbf{Capitolato C3: Fossdot -- Smart Speaker Open Source}\par}

\vfill
\begin{tabular}[t]{r|l}
\textbf{Versione} & \docversion \\
\textbf{Tipo} & Documento esterno \\
\textbf{Destinatari} & \emph{Gruppo Bending Forks} \\
 & \emph{Prof. Tullio Vardanega} \\
 & \emph{Prof. Riccardo Cardin} \\
\end{tabular}

\vspace{12mm}
{\large\emph{\textbf{Abstract dei contenuti:}}}\\[1mm]
\begin{minipage}{150mm}\centering
Il presente documento raccoglie e formalizza la definizione dei termini tecnici, degli acronimi e del gergo di dominio adottati dal gruppo Bending Forks nello sviluppo del progetto FossDot. Lo scopo è prevenire ambiguità e favorire l'uniformità del vocabolario condiviso tra tutti gli stakeholder.
\end{minipage}
\vspace*{6mm}
\end{titlepage}

% ---------- Indice ----------
\vspace*{2mm}
{\fontsize{22}{26}\selectfont\bfseries Indice\par}
\vspace{6mm}
\makeatletter\@starttoc{toc}\makeatother
\newpage


% ---------- Registro delle versioni ----------
\section{Registro delle versioni}

\begin{center}
\begin{tabularx}{\linewidth}{
  >{\hsize=0.55\hsize\raggedright\arraybackslash}X
  >{\hsize=0.75\hsize\raggedright\arraybackslash}X
  >{\hsize=0.90\hsize\raggedright\arraybackslash}X
  >{\hsize=0.85\hsize\raggedright\arraybackslash}X
  >{\hsize=1.95\hsize\raggedright\arraybackslash}X
}
\rowcolor{bfblue}\textcolor{white}{\textbf{Versione}} & 
\textcolor{white}{\textbf{Data}} & 
\textcolor{white}{\textbf{Autore}} & 
\textcolor{white}{\textbf{Verificatore}} & 
\textcolor{white}{\textbf{Descrizione}} \\
@@CHANGELOG_ROWS@@
\end{tabularx}
\end{center}

\newpage

% ---------- Introduzione ----------
\section{Introduzione}

Il presente documento definisce in modo chiaro e univoco i vocaboli specifici, gli acronimi e i concetti cardine impiegati nell'arco dell'intero ciclo di vita del progetto. L'adozione di un glossario garantisce coerenza terminologica sia nelle comunicazioni interne al team sia nella documentazione destinata ai committenti, ai proponenti e ai revisori.

Come previsto dalle \emph{Norme di progetto}, la prima occorrenza di un termine presente nel Glossario è scritta in corsivo con una G a pedice, ad esempio: \emph{termine}\textsubscript{\scriptsize G}.

% ---------- Inizio glossario ----------

@@BODY@@

\end{document}"""


def build_html(meta, entries):
    payload = json.dumps(entries, ensure_ascii=False).replace("</", "<\\/")
    page = HTML_TEMPLATE
    for key, value in (
        ("@@DATA@@", payload),
        ("@@SITE_CSS@@", SITE_CSS),
        ("@@FAVICON@@", FAVICON),
        ("@@PROJECT@@", meta.get("project", "")),
        ("@@GROUP@@", meta.get("group", "")),
        ("@@COURSE@@", meta.get("course", "")),
        ("@@VERSION@@", meta.get("version", "")),
    ):
        page = page.replace(key, value)
    HTML_OUT.write_text(page, encoding="utf-8", newline="\n")


def build_tex(meta, changelog, entries):
    pattern, alias_to_slug, alias_to_owner = build_link_matcher(entries)

    changelog_rows = [
        " & ".join(
            tex_escape(row.get(col, ""))
            for col in ("version", "date", "author", "verifier", "description")
        )
        + r" \\ \arrayrulecolor{bfline}\hline"
        for row in changelog
    ]
    if not changelog_rows:
        changelog_rows = [
            tex_escape(meta.get("version", ""))
            + r" & - & - & - & Versione corrente \\ \arrayrulecolor{bfline}\hline"
        ]

    body, current = [], None
    for e in entries:
        letter = group_letter(e["term"])
        if letter != current:
            current = letter
            body.append("\\glossarysection{" + tex_escape(letter) + "}")
        slug = slugify(e["term"])
        heading = tex_escape(e["term"])
        if e["type"] == "abbr" and e.get("expansion"):
            heading += " (" + tex_escape(e["expansion"]) + ")"
        linked_def = linkify_tex(e["definition"], e["term"], pattern, alias_to_slug, alias_to_owner)
        body.append(
            f"\\raisebox{{55pt}}[0pt][0pt]{{\\hypertarget{{term-{slug}}}{{}}}}"
            f"\\glossterm{{{heading}}}{{{linked_def}}}"
        )

    source = TEX_TEMPLATE
    for key, value in (
        ("@@VERSION@@", tex_escape(meta.get("version", ""))),
        ("@@DATE@@", tex_escape(meta.get("date", ""))),
        ("@@CHANGELOG_ROWS@@", "\n".join(changelog_rows)),
        ("@@BODY@@", "\n\n".join(body)),
    ):
        source = source.replace(key, value)
    TEX_OUT.parent.mkdir(parents=True, exist_ok=True)
    TEX_OUT.write_text(source, encoding="utf-8", newline="\n")


def clean_aux():
    for ext in AUX_EXTENSIONS:
        (TEX_OUT.parent / (TEX_OUT.stem + ext)).unlink(missing_ok=True)


def build_pdf():
    if shutil.which("latexmk"):
        commands = [["latexmk", "-g", "-pdf", "-interaction=nonstopmode", "-halt-on-error", TEX_OUT.name]]
    elif shutil.which("pdflatex"):
        single = ["pdflatex", "-interaction=nonstopmode", "-halt-on-error", TEX_OUT.name]
        commands = [single, single]
    else:
        print("errore: nessun compilatore LaTeX trovato (serve latexmk o pdflatex)", file=sys.stderr)
        return False

    PDF_OUT.unlink(missing_ok=True)
    for command in commands:
        result = subprocess.run(command, cwd=TEX_OUT.parent, capture_output=True, text=True, errors="replace")
        if result.returncode != 0:
            print("errore: compilazione LaTeX fallita", file=sys.stderr)
            print("\n".join(result.stdout.splitlines()[-30:]), file=sys.stderr)
            return False

    if not PDF_OUT.exists():
        print("errore: PDF non generato", file=sys.stderr)
        return False
    clean_aux()
    return True


def run():
    meta, changelog, entries = load()
    errors = validate(entries)
    if errors:
        for e in errors:
            print("errore: " + e, file=sys.stderr)
        return 1

    entries.sort(key=lambda e: (sort_key(e["term"]), e["term"]))
    save_sorted_json(meta, changelog, entries)

    build_html(meta, entries)
    print(f"{HTML_OUT.name}: {len(entries)} voci")
    build_tex(meta, changelog, entries)
    print(f"{TEX_OUT.name}: generato")
    if not build_pdf():
        return 1
    print(f"{PDF_OUT.name}: generato")
    return 0


def watch():
    print(f"in ascolto su {SOURCE.name} (Ctrl+C per uscire)")
    last = None
    try:
        while True:
            try:
                stamp = SOURCE.stat().st_mtime_ns
                if stamp != last:
                    time.sleep(0.3)
                    last = SOURCE.stat().st_mtime_ns
                    run()
            except (OSError, ValueError, KeyError) as exc:
                print(f"errore: {exc}", file=sys.stderr)
            time.sleep(0.5)
    except KeyboardInterrupt:
        return 0


def main():
    parser = argparse.ArgumentParser(description="Genera HTML, LaTeX e PDF del glossario")
    parser.add_argument("--watch", action="store_true", help="rigenera ad ogni salvataggio di glossary.json")
    args = parser.parse_args()
    return watch() if args.watch else run()


if __name__ == "__main__":
    sys.exit(main())