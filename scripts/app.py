#!/usr/bin/env python3
"""
app.py — Simple Flask web UI for querying the Football Linked Data SPARQL endpoint.
"""

from pathlib import Path
from flask import Flask, request, jsonify, render_template_string
from rdflib import ConjunctiveGraph

BASE_DIR   = Path(__file__).parent.parent
LINKED_TTL = BASE_DIR / "data" / "linked" / "football_linked.ttl"
ONTO_TTL   = BASE_DIR / "ontology" / "football.ttl"

PREFIX_BLOCK = """\
PREFIX onto:   <http://semantic-football.org/ontology#>
PREFIX data:   <http://semantic-football.org/data/>
PREFIX rdf:    <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:   <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:    <http://www.w3.org/2002/07/owl#>
PREFIX xsd:    <http://www.w3.org/2001/XMLSchema#>
PREFIX schema: <https://schema.org/>
PREFIX foaf:   <http://xmlns.com/foaf/0.1/>
PREFIX skos:   <http://www.w3.org/2004/02/skos/core#>
PREFIX dc:     <http://purl.org/dc/elements/1.1/>
"""

EXAMPLE_QUERIES = {
    "all_clubs": {
        "label": "All Clubs",
        "query": """SELECT ?name ?city ?founded
WHERE {
    ?club a onto:FootballClub ;
          onto:name  ?name ;
          onto:city  ?city .
    OPTIONAL { ?club onto:founded ?founded }
}
ORDER BY ?name"""
    },
    "top_scorers": {
        "label": "Top Scorers",
        "query": """SELECT ?playerName ?clubName (COUNT(?goal) AS ?goals)
WHERE {
    ?goal a onto:Goal ;
          onto:scoredBy      ?player ;
          onto:scoredForTeam ?club .
    ?player onto:name ?playerName .
    ?club   onto:name ?clubName .
}
GROUP BY ?playerName ?clubName
ORDER BY DESC(?goals)
LIMIT 10"""
    },
    "match_results": {
        "label": "Match Results",
        "query": """SELECT ?homeClub ?awayClub ?homeScore ?awayScore ?matchDate ?week
WHERE {
    ?match a onto:Match ;
           onto:homeTeam  ?home ;
           onto:awayTeam  ?away ;
           onto:homeScore ?homeScore ;
           onto:awayScore ?awayScore ;
           onto:matchDate ?matchDate ;
           onto:matchWeek ?week .
    ?home onto:shortName ?homeClub .
    ?away onto:shortName ?awayClub .
}
ORDER BY ?matchDate"""
    },
    "squad_arsenal": {
        "label": "Arsenal Squad",
        "query": """SELECT ?playerName ?position ?nationality ?jersey
WHERE {
    ?player a onto:Player ;
            onto:name     ?playerName ;
            onto:playsFor <http://semantic-football.org/data/club/arsenal> .
    OPTIONAL { ?player onto:hasPosition ?pos . ?pos onto:shortName ?position }
    OPTIONAL { ?player onto:hasNationality ?nat . ?nat onto:name ?nationality }
    OPTIONAL { ?player onto:jerseyNumber ?jersey }
}
ORDER BY ?position ?playerName"""
    },
    "high_value_transfers": {
        "label": "Big Transfers (>€50M)",
        "query": """SELECT ?playerName ?toClub ?fee ?date
WHERE {
    ?transfer a onto:Transfer ;
              onto:transferredPlayer ?player ;
              onto:toClub ?to ;
              onto:transferFee ?fee .
    FILTER (?fee > 50)
    ?player onto:name ?playerName .
    ?to     onto:name ?toClub .
    OPTIONAL { ?transfer onto:transferDate ?date }
}
ORDER BY DESC(?fee)"""
    },
    "stadiums": {
        "label": "Stadiums",
        "query": """SELECT ?stadiumName ?city ?capacity ?geoCity
WHERE {
    ?stadium a onto:Stadium ;
             onto:name     ?stadiumName ;
             onto:city     ?city ;
             onto:capacity ?capacity .
    OPTIONAL { ?stadium schema:location ?geoCity }
}
ORDER BY DESC(?capacity)"""
    },
    "external_links": {
        "label": "DBpedia Links (5★)",
        "query": """SELECT ?clubName ?dbpediaURI
WHERE {
    ?club a onto:FootballClub ;
          onto:name  ?clubName ;
          owl:sameAs ?dbpediaURI .
    FILTER(CONTAINS(STR(?dbpediaURI), "dbpedia.org"))
}
ORDER BY ?clubName"""
    },
    "wikidata_players": {
        "label": "Wikidata Links (5★)",
        "query": """SELECT ?playerName ?wikidataURI
WHERE {
    ?player a onto:Player ;
            onto:name  ?playerName ;
            owl:sameAs ?wikidataURI .
    FILTER(CONTAINS(STR(?wikidataURI), "wikidata.org"))
}
ORDER BY ?playerName
LIMIT 15"""
    },
    "managers": {
        "label": "Managers",
        "query": """SELECT ?managerName ?clubName ?nationality
WHERE {
    ?manager a onto:Manager ;
             onto:name    ?managerName ;
             onto:country ?nationality .
    ?club    a onto:FootballClub ;
             onto:name      ?clubName ;
             onto:managedBy ?manager .
}
ORDER BY ?managerName"""
    },
    "count_types": {
        "label": "Entity Counts",
        "query": """SELECT ?type (COUNT(?entity) AS ?count)
WHERE {
    ?entity a ?type .
    FILTER(STRSTARTS(STR(?type), "http://semantic-football.org/ontology#"))
}
GROUP BY ?type
ORDER BY DESC(?count)"""
    },
    "goals_per_match": {
        "label": "Goals per Match",
        "query": """SELECT ?homeClub ?awayClub ?matchDate ?homeScore ?awayScore
       (?homeScore + ?awayScore AS ?total)
WHERE {
    ?match a onto:Match ;
           onto:homeTeam  ?home ;
           onto:awayTeam  ?away ;
           onto:homeScore ?homeScore ;
           onto:awayScore ?awayScore ;
           onto:matchDate ?matchDate .
    ?home onto:shortName ?homeClub .
    ?away onto:shortName ?awayClub .
}
ORDER BY DESC(?homeScore + ?awayScore)"""
    },
    "arsenal_goals": {
        "label": "Arsenal Goals Detail",
        "query": """SELECT ?playerName ?homeClub ?awayClub ?minute ?isPenalty ?matchDate
WHERE {
    ?goal a onto:Goal ;
          onto:scoredBy      ?player ;
          onto:scoredForTeam <http://semantic-football.org/data/club/arsenal> ;
          onto:scoredInMatch ?match ;
          onto:goalMinute    ?minute ;
          onto:isPenalty     ?isPenalty .
    ?player onto:name      ?playerName .
    ?match  onto:homeTeam  ?home ;
            onto:awayTeam  ?away ;
            onto:matchDate ?matchDate .
    ?home onto:shortName ?homeClub .
    ?away onto:shortName ?awayClub .
}
ORDER BY ?matchDate ?minute"""
    },
}

HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Football Linked Data — SPARQL Explorer</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', system-ui, sans-serif;
    background: #0f1117;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }

  /* ── Header ── */
  header {
    background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
    border-bottom: 1px solid #2d3748;
    padding: 16px 24px;
    display: flex;
    align-items: center;
    gap: 14px;
  }
  header .logo { font-size: 28px; }
  header h1 { font-size: 20px; font-weight: 700; color: #f7fafc; }
  header p  { font-size: 13px; color: #718096; margin-top: 2px; }
  .badge {
    margin-left: auto;
    background: #2d6a4f;
    color: #b7e4c7;
    font-size: 11px;
    font-weight: 700;
    padding: 4px 10px;
    border-radius: 20px;
    letter-spacing: .5px;
  }

  /* ── Layout ── */
  .main { display: flex; flex: 1; overflow: hidden; height: calc(100vh - 65px); }

  /* ── Sidebar ── */
  .sidebar {
    width: 220px;
    min-width: 220px;
    background: #141820;
    border-right: 1px solid #2d3748;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }
  .sidebar-title {
    padding: 14px 16px 8px;
    font-size: 11px;
    font-weight: 700;
    color: #4a5568;
    letter-spacing: 1px;
    text-transform: uppercase;
  }
  .example-btn {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    color: #a0aec0;
    font-size: 13px;
    padding: 9px 16px;
    cursor: pointer;
    border-left: 3px solid transparent;
    transition: all .15s;
  }
  .example-btn:hover  { background: #1e2433; color: #e2e8f0; }
  .example-btn.active { background: #1e2d45; color: #63b3ed; border-left-color: #3182ce; }

  /* ── Editor panel ── */
  .editor-panel {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .query-area {
    padding: 16px;
    border-bottom: 1px solid #2d3748;
    background: #141820;
  }
  .query-area label {
    font-size: 11px;
    font-weight: 700;
    color: #4a5568;
    letter-spacing: 1px;
    text-transform: uppercase;
    display: block;
    margin-bottom: 8px;
  }
  textarea#query {
    width: 100%;
    height: 170px;
    background: #0d1117;
    border: 1px solid #2d3748;
    border-radius: 8px;
    color: #e2e8f0;
    font-family: 'JetBrains Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 13px;
    line-height: 1.6;
    padding: 12px;
    resize: vertical;
    outline: none;
    transition: border-color .2s;
  }
  textarea#query:focus { border-color: #3182ce; }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 10px 16px;
    background: #141820;
    border-bottom: 1px solid #2d3748;
  }
  #run-btn {
    background: #2b6cb0;
    color: #fff;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 7px;
    transition: background .2s;
  }
  #run-btn:hover    { background: #2c5282; }
  #run-btn:disabled { background: #2d3748; cursor: not-allowed; }
  #clear-btn {
    background: none;
    border: 1px solid #2d3748;
    color: #718096;
    border-radius: 6px;
    padding: 7px 14px;
    font-size: 13px;
    cursor: pointer;
    transition: all .15s;
  }
  #clear-btn:hover { border-color: #4a5568; color: #a0aec0; }

  .stats { margin-left: auto; font-size: 12px; color: #4a5568; }
  .stats span { color: #63b3ed; font-weight: 600; }

  /* ── Results ── */
  .results-area {
    flex: 1;
    overflow: auto;
    padding: 16px;
  }

  .result-meta {
    font-size: 12px;
    color: #718096;
    margin-bottom: 10px;
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .result-meta .pill {
    background: #1a2035;
    border: 1px solid #2d3748;
    border-radius: 12px;
    padding: 2px 10px;
    font-size: 11px;
  }
  .result-meta .pill.green { border-color: #276749; color: #9ae6b4; }
  .result-meta .pill.red   { border-color: #742a2a; color: #fc8181; }

  table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
  }
  thead th {
    background: #1a2035;
    color: #90cdf4;
    font-weight: 600;
    padding: 10px 14px;
    text-align: left;
    border-bottom: 2px solid #2d3748;
    position: sticky;
    top: 0;
    white-space: nowrap;
  }
  tbody tr { border-bottom: 1px solid #1e2535; }
  tbody tr:hover { background: #141c2b; }
  tbody td {
    padding: 9px 14px;
    color: #cbd5e0;
    max-width: 360px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  td.uri  { color: #76e4f7; font-size: 12px; }
  td.num  { color: #fbd38d; font-weight: 600; }
  td.bool-true  { color: #9ae6b4; }
  td.bool-false { color: #718096; }

  /* DESCRIBE output */
  .describe-block {
    background: #0d1117;
    border: 1px solid #2d3748;
    border-radius: 8px;
    padding: 14px;
    font-family: monospace;
    font-size: 12.5px;
    line-height: 1.8;
  }
  .describe-block .subject  { color: #76e4f7; font-weight: 700; }
  .describe-block .pred     { color: #d6bcfa; }
  .describe-block .obj      { color: #fbd38d; }
  .describe-block .obj.lit  { color: #9ae6b4; }

  /* ASK result */
  .ask-result {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    font-size: 24px;
    font-weight: 700;
    padding: 20px;
  }
  .ask-result.true  { color: #48bb78; }
  .ask-result.false { color: #fc8181; }

  /* Error / empty */
  .msg-box {
    padding: 16px;
    border-radius: 8px;
    font-size: 13px;
    margin-top: 4px;
  }
  .msg-box.error { background: #2d1515; border: 1px solid #742a2a; color: #fc8181; }
  .msg-box.empty { background: #1a1f2e; border: 1px solid #2d3748; color: #4a5568; }

  /* Spinner */
  .spinner {
    width: 16px; height: 16px;
    border: 2px solid #4a5568;
    border-top-color: #63b3ed;
    border-radius: 50%;
    animation: spin .7s linear infinite;
    display: none;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  #run-btn.loading .spinner { display: block; }
  #run-btn.loading .btn-text { display: none; }
</style>
</head>
<body>

<header>
  <span class="logo">⚽</span>
  <div>
    <h1>Football Linked Data</h1>
    <p>Premier League 2023–24 &nbsp;·&nbsp; SPARQL Explorer</p>
  </div>
  <span class="badge">★★★★★ 5-Star Linked Data</span>
</header>

<div class="main">

  <!-- Sidebar -->
  <aside class="sidebar">
    <div class="sidebar-title">Example Queries</div>
    {% for key, q in examples.items() %}
    <button class="example-btn" onclick="loadExample('{{ key }}')" id="btn-{{ key }}">
      {{ q.label }}
    </button>
    {% endfor %}
  </aside>

  <!-- Editor + Results -->
  <div class="editor-panel">

    <div class="query-area">
      <label>SPARQL Query</label>
      <textarea id="query" spellcheck="false" placeholder="Type a SPARQL query here…&#10;&#10;Prefixes (onto:, data:, owl:, foaf:, schema:, skos:) are added automatically."></textarea>
    </div>

    <div class="toolbar">
      <button id="run-btn" onclick="runQuery()">
        <span class="btn-text">▶ Run Query</span>
        <div class="spinner"></div>
      </button>
      <button id="clear-btn" onclick="clearAll()">Clear</button>
      <div class="stats">Dataset: <span>{{ triple_count }}</span> triples</div>
    </div>

    <div class="results-area" id="results">
      <div class="msg-box empty">Select an example from the sidebar or write a query above, then click <strong>Run Query</strong>.</div>
    </div>

  </div>
</div>

<script>
const EXAMPLES = {{ examples_json | safe }};
let activeBtn = null;

function loadExample(key) {
  const q = EXAMPLES[key];
  if (!q) return;
  document.getElementById('query').value = q.query;
  // highlight active button
  if (activeBtn) activeBtn.classList.remove('active');
  activeBtn = document.getElementById('btn-' + key);
  if (activeBtn) activeBtn.classList.add('active');
  runQuery();
}

function clearAll() {
  document.getElementById('query').value = '';
  document.getElementById('results').innerHTML =
    '<div class="msg-box empty">Query cleared.</div>';
  if (activeBtn) { activeBtn.classList.remove('active'); activeBtn = null; }
}

async function runQuery() {
  const query = document.getElementById('query').value.trim();
  if (!query) return;

  const btn = document.getElementById('run-btn');
  btn.disabled = true;
  btn.classList.add('loading');

  try {
    const res  = await fetch('/query', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    const data = await res.json();
    renderResult(data);
  } catch (e) {
    document.getElementById('results').innerHTML =
      `<div class="msg-box error">Network error: ${e.message}</div>`;
  } finally {
    btn.disabled = false;
    btn.classList.remove('loading');
  }
}

function shortenURI(uri) {
  const MAP = [
    ['http://semantic-football.org/data/',        'data:'],
    ['http://semantic-football.org/ontology#',    'onto:'],
    ['http://www.wikidata.org/entity/',           'wd:'],
    ['http://dbpedia.org/resource/',              'dbr:'],
    ['https://sws.geonames.org/',                 'geo:'],
    ['https://schema.org/',                       'schema:'],
    ['http://www.w3.org/2002/07/owl#',            'owl:'],
    ['http://xmlns.com/foaf/0.1/',                'foaf:'],
    ['http://www.w3.org/1999/02/22-rdf-syntax-ns#', 'rdf:'],
  ];
  for (const [long, short] of MAP) {
    if (uri.startsWith(long)) return short + uri.slice(long.length);
  }
  return uri;
}

function renderResult(data) {
  const out = document.getElementById('results');

  if (data.error) {
    out.innerHTML = `<div class="msg-box error"><strong>SPARQL Error:</strong><br><pre style="margin-top:8px;white-space:pre-wrap">${escHtml(data.error)}</pre></div>`;
    return;
  }

  if (data.type === 'ask') {
    const cls = data.result ? 'true' : 'false';
    const icon = data.result ? '✔' : '✘';
    out.innerHTML = `
      <div class="result-meta"><span class="pill">ASK</span></div>
      <div class="ask-result ${cls}">${icon} ${data.result}</div>`;
    return;
  }

  if (data.type === 'describe') {
    let html = `<div class="result-meta"><span class="pill">DESCRIBE</span><span class="pill green">${data.triples.length} triple(s)</span></div>`;
    html += '<div class="describe-block">';
    let lastSubj = null;
    for (const [s, p, o, oType] of data.triples) {
      const ss = shortenURI(s), ps = shortenURI(p);
      const os = oType === 'uri' ? shortenURI(o) : o;
      const objCls = oType === 'uri' ? 'obj' : 'obj lit';
      if (s !== lastSubj) {
        if (lastSubj !== null) html += '<br>';
        html += `<span class="subject">${escHtml(ss)}</span><br>`;
        lastSubj = s;
      }
      html += `&nbsp;&nbsp;&nbsp;&nbsp;<span class="pred">${escHtml(ps)}</span> <span class="${objCls}">${escHtml(os)}</span><br>`;
    }
    html += '</div>';
    out.innerHTML = html;
    return;
  }

  // SELECT
  if (!data.rows || data.rows.length === 0) {
    out.innerHTML = `<div class="result-meta"><span class="pill">SELECT</span></div><div class="msg-box empty">No results returned.</div>`;
    return;
  }

  const pillCls = data.rows.length > 0 ? 'green' : '';
  let html = `<div class="result-meta"><span class="pill">SELECT</span><span class="pill ${pillCls}">${data.rows.length} row(s)</span></div>`;
  html += '<table><thead><tr>';
  for (const col of data.vars) {
    html += `<th>${escHtml(col)}</th>`;
  }
  html += '</tr></thead><tbody>';

  for (const row of data.rows) {
    html += '<tr>';
    for (const col of data.vars) {
      const cell = row[col];
      if (cell === null || cell === undefined) {
        html += '<td style="color:#4a5568">—</td>';
      } else if (cell.type === 'uri') {
        const short = shortenURI(cell.value);
        const isExternal = cell.value.startsWith('http://dbpedia') ||
                           cell.value.startsWith('http://www.wikidata') ||
                           cell.value.startsWith('https://sws.geonames');
        if (isExternal) {
          html += `<td class="uri"><a href="${escHtml(cell.value)}" target="_blank" style="color:#76e4f7;text-decoration:none" title="${escHtml(cell.value)}">${escHtml(short)} ↗</a></td>`;
        } else {
          html += `<td class="uri" title="${escHtml(cell.value)}">${escHtml(short)}</td>`;
        }
      } else if (cell.type === 'literal') {
        const v = cell.value;
        const isNum = !isNaN(v) && v !== '';
        const isBool = v === 'true' || v === 'false';
        if (isNum) {
          html += `<td class="num">${escHtml(v)}</td>`;
        } else if (isBool) {
          html += `<td class="bool-${v}">${v === 'true' ? '✔' : '✘'}</td>`;
        } else {
          html += `<td title="${escHtml(v)}">${escHtml(v)}</td>`;
        }
      } else {
        html += `<td>${escHtml(String(cell.value))}</td>`;
      }
    }
    html += '</tr>';
  }
  html += '</tbody></table>';
  out.innerHTML = html;
}

function escHtml(s) {
  return String(s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;')
    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// Ctrl+Enter to run
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') runQuery();
});
</script>
</body>
</html>"""

# ── Flask app ────────────────────────────────────────────────
app = Flask(__name__)

print("Loading RDF graph…")
g = ConjunctiveGraph()
if ONTO_TTL.exists():
    g.parse(str(ONTO_TTL), format="turtle")
g.parse(str(LINKED_TTL), format="turtle")
TRIPLE_COUNT = len(g)
print(f"Loaded {TRIPLE_COUNT} triples.")


def fmt_value(node):
    from rdflib import URIRef, Literal, BNode
    if node is None:
        return None
    if isinstance(node, URIRef):
        return {"type": "uri",     "value": str(node)}
    if isinstance(node, Literal):
        return {"type": "literal", "value": str(node)}
    return {"type": "bnode",   "value": str(node)}


@app.route("/")
def index():
    import json
    examples_json = json.dumps({k: {"query": v["query"], "label": v["label"]}
                                 for k, v in EXAMPLE_QUERIES.items()})
    return render_template_string(
        HTML,
        examples=EXAMPLE_QUERIES,
        examples_json=examples_json,
        triple_count=f"{TRIPLE_COUNT:,}",
    )


@app.route("/query", methods=["POST"])
def query():
    from rdflib import URIRef, Literal
    data = request.get_json(force=True)
    raw  = data.get("query", "").strip()
    if not raw:
        return jsonify({"error": "Empty query"})

    full_query = PREFIX_BLOCK + "\n" + raw

    try:
        result = g.query(full_query)
    except Exception as e:
        return jsonify({"error": str(e)})

    qtype = result.type

    if qtype == "ASK":
        return jsonify({"type": "ask", "result": bool(result.askAnswer)})

    if qtype in ("DESCRIBE", "CONSTRUCT"):
        triples = []
        for s, p, o in sorted(result.graph, key=lambda t: (str(t[0]), str(t[1]))):
            oType = "uri" if isinstance(o, URIRef) else "literal"
            triples.append([str(s), str(p), str(o), oType])
        return jsonify({"type": "describe", "triples": triples})

    # SELECT
    vars_ = [str(v) for v in result.vars]
    rows  = []
    for row in result:
        r = {}
        for v in result.vars:
            r[str(v)] = fmt_value(row[v])
        rows.append(r)
    return jsonify({"type": "select", "vars": vars_, "rows": rows})


if __name__ == "__main__":
    import webbrowser, threading
    url = "http://127.0.0.1:5000"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    print(f"\n  Open → {url}\n  Press Ctrl+C to stop.\n")
    app.run(debug=False, port=5000)
