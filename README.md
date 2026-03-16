# Football Semantic Web — Linked Data Assignment

> **Domain:** Football (Premier League 2023–24)

This project implements all five Linked Data stars for the **football domain**, including an OWL ontology, raw data collection, RDF transformation, cross-dataset linking, and an interactive SPARQL terminal.

---

## Linked Data Stars

| ★ | Standard | This project |
|---|----------|-------------|
| ★ | Data available on the web | RDF files served from `data/` |
| ★★ | Machine-readable structured data | Turtle / N-Triples |
| ★★★ | Non-proprietary open format | RDF (W3C standard) |
| ★★★★ | HTTP URIs for everything | All entities at `http://semantic-football.org/data/…` |
| ★★★★★ | Links to other datasets | `owl:sameAs` → DBpedia & Wikidata; `schema:sameAs`; `skos:exactMatch`; GeoNames city links |

---

## Project Structure

```
semantic-web/
├── ontology/
│   └── football.ttl          ← OWL ontology (classes, properties)
├── data/
│   ├── raw/                  ← Original CSV data files
│   │   ├── clubs.csv
│   │   ├── players.csv
│   │   ├── managers.csv
│   │   ├── stadiums.csv
│   │   ├── matches.csv
│   │   ├── goals.csv
│   │   ├── transfers.csv
│   │   ├── leagues.csv
│   │   └── seasons.csv
│   ├── rdf/                  ← 4★ RDF output
│   │   ├── football_data.ttl
│   │   └── football_data.nt
│   └── linked/               ← 5★ linked output
│       ├── football_linked.ttl
│       └── football_linked.nt
├── scripts/
│   ├── transform.py          ← CSV → RDF (4★)
│   ├── link.py               ← Add external links (5★)
│   ├── sparql_terminal.py    ← Interactive SPARQL interface
│   └── run_all.py            ← Full pipeline runner
├── queries/
│   └── example_queries.sparql ← 20 example SPARQL queries
└── requirements.txt
```

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the full pipeline (transform → link → terminal)
python3 scripts/run_all.py

# Or run each step individually:
python3 scripts/transform.py       # produces data/rdf/football_data.ttl
python3 scripts/link.py            # produces data/linked/football_linked.ttl
python3 scripts/sparql_terminal.py # interactive SPARQL terminal
```

---

## Step 1 — Ontology (`ontology/football.ttl`)

The ontology is written in **OWL 2 / Turtle** and defines:

### Classes
| Class | Description |
|-------|-------------|
| `onto:FootballClub` | A professional football club |
| `onto:Player` | A professional player |
| `onto:Manager` | A team manager / head coach |
| `onto:Match` | A scheduled match between two clubs |
| `onto:League` | A football league / competition |
| `onto:Season` | A football season (e.g. 2023-24) |
| `onto:Stadium` | A football stadium |
| `onto:Position` | Playing position (GK / DF / MF / FW) |
| `onto:Goal` | A goal scored during a match |
| `onto:Transfer` | A player transfer between clubs |
| `onto:Nationality` | A player's nationality |

### Key Object Properties
`playsFor`, `hasPosition`, `hasNationality`, `managedBy`, `hasStadium`,
`participatesIn`, `homeTeam`, `awayTeam`, `wonBy`, `scoredBy`, `scoredInMatch`,
`scoredForTeam`, `transferredPlayer`, `fromClub`, `toClub`, `inSeason`, `partOfLeague`, `partOfSeason`

### Key Datatype Properties
`name`, `dateOfBirth`, `jerseyNumber`, `height`, `marketValue`, `founded`,
`city`, `country`, `capacity`, `matchDate`, `matchWeek`, `homeScore`, `awayScore`,
`goalMinute`, `isPenalty`, `isOwnGoal`, `transferFee`, `transferDate`

---

## Step 2 — Raw Data

Manually curated CSV files covering the **2023-24 Premier League** season:

- **6 clubs** — Manchester City, Arsenal, Liverpool, Aston Villa, Tottenham, Chelsea
- **30 players** — 5 per club with real biographical data
- **6 managers**
- **6 stadiums**
- **15 matches** with scorelines
- **45 goals** with scorer, minute, and penalty flags
- **10 transfers** including real fees (Enzo Fernández €121M, Declan Rice €116.6M…)

---

## Step 3 — 4★ Transformation (`scripts/transform.py`)

Converts all CSVs into RDF Turtle using **HTTP URIs** for every entity:

```
http://semantic-football.org/data/club/arsenal
http://semantic-football.org/data/player/erling_haaland
http://semantic-football.org/data/match/m001
```

Outputs **1 238 triples** in `data/rdf/football_data.ttl`.

---

## Step 4 — 5★ External Links (`scripts/link.py`)

Augments the 4★ graph with cross-dataset links:

| Link type | Target dataset | Example |
|-----------|---------------|---------|
| `owl:sameAs` | DBpedia | Arsenal → `dbr:Arsenal_F.C.` |
| `owl:sameAs` | Wikidata | Haaland → `wd:Q61908496` |
| `schema:sameAs` | Schema.org consumers | (mirrors every owl:sameAs) |
| `skos:exactMatch` | DBpedia | (all DBpedia URIs) |
| `schema:location` | GeoNames | London → `geonames:2643743` |

Total: **1 449 triples** in `data/linked/football_linked.ttl`.

---

## Step 5 — SPARQL Terminal (`scripts/sparql_terminal.py`)

An interactive Read-Eval-Print Loop (REPL) over the in-memory RDF graph.

```
============================================================
 Football Linked Data — SPARQL Terminal
============================================================
 Dataset loaded: 1666 triples
 Type  :help  for available commands.

SPARQL> :run top_scorers

  [top_scorers] Top goal scorers in the dataset (all matches)

+--------------------+--------------------+-------+
| playerName         | clubName           | goals |
+--------------------+--------------------+-------+
| Bukayo Saka        | Arsenal FC         | 6     |
| Erling Haaland     | Manchester City FC | 6     |
| Darwin Nunez       | Liverpool FC       | 5     |
...
```

### Terminal Commands

| Command | Description |
|---------|-------------|
| `:help` | Show help |
| `:examples` | List all 14 named example queries |
| `:run <name>` | Execute a named example query |
| `:show <name>` | Print the SPARQL source of a named query |
| `:prefixes` | Print the auto-prepended PREFIX block |
| `:count` | Show total triple count |
| `:quit` | Exit |

### Named Example Queries

| Name | Description |
|------|-------------|
| `all_clubs` | All clubs with city and founding year |
| `squad` | Arsenal full squad (position, nationality, jersey) |
| `top_scorers` | Top 10 goal scorers |
| `match_results` | All 15 match results with scores |
| `high_value_transfers` | Transfers > €50M |
| `stadiums` | Stadiums with capacity and GeoNames link |
| `external_links` | DBpedia `owl:sameAs` links for clubs |
| `wikidata_players` | Players with Wikidata links |
| `matches_per_club` | Home and away match count per club |
| `goals_per_match` | Matches ordered by total goals |
| `managers` | All managers with club and nationality |
| `arsenal_goals_detail` | All Arsenal goals (minute, penalty flag) |
| `describe_haaland` | DESCRIBE — all triples about Haaland |
| `count_triples` | Entity counts by ontology type |

### Ad-hoc Query Example

```sparql
SPARQL> SELECT ?name ?marketValue
     …  WHERE {
     …      ?p a onto:Player ;
     …         onto:name        ?name ;
     …         onto:marketValue ?marketValue .
     …  }
     …  ORDER BY DESC(?marketValue)
     …  LIMIT 5
     …
```
*(press Enter on a blank line to submit)*

---

## External Dataset Links

| Dataset | URL |
|---------|-----|
| DBpedia | https://dbpedia.org |
| Wikidata | https://www.wikidata.org |
| GeoNames | https://sws.geonames.org |
| Schema.org | https://schema.org |
