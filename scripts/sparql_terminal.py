#!/usr/bin/env python3
"""
sparql_terminal.py — Interactive SPARQL terminal for the Football Linked Data dataset.

Features
--------
• Loads the full 5★ linked dataset into an in-memory rdflib ConjunctiveGraph.
• Provides a REPL (Read-Eval-Print Loop) for ad-hoc SPARQL queries.
• Ships with named example queries you can run with  :run <name>.
• Outputs results as a formatted table.
• Type  :help  for all commands.

Usage
-----
    python3 scripts/sparql_terminal.py
    python3 scripts/sparql_terminal.py --dataset 4star   # use 4★ graph
"""

import argparse
import sys
import textwrap
from pathlib import Path

from rdflib import ConjunctiveGraph, Namespace
from rdflib.plugins.sparql.processor import prepareQuery

BASE_DIR   = Path(__file__).parent.parent
LINKED_TTL = BASE_DIR / "data" / "linked" / "football_linked.ttl"
RDF_TTL    = BASE_DIR / "data" / "rdf"    / "football_data.ttl"
ONTO_TTL   = BASE_DIR / "ontology"        / "football.ttl"

# ─────────────────────────────────────────────────────────────
#  Prefix block prepended to every user query automatically
# ─────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────
#  Named example queries
# ─────────────────────────────────────────────────────────────
EXAMPLE_QUERIES = {

    "all_clubs": {
        "description": "List all football clubs with city and year founded",
        "query": """\
SELECT ?name ?city ?founded
WHERE {
    ?club a onto:FootballClub ;
          onto:name    ?name ;
          onto:city    ?city .
    OPTIONAL { ?club onto:founded ?founded }
}
ORDER BY ?name
""",
    },

    "squad": {
        "description": "Full squad for Arsenal — name, position, nationality, jersey number",
        "query": """\
SELECT ?playerName ?position ?nationality ?jersey
WHERE {
    ?player a onto:Player ;
            onto:name         ?playerName ;
            onto:playsFor     <http://semantic-football.org/data/club/arsenal> .
    OPTIONAL { ?player onto:hasPosition  ?pos .
               ?pos    onto:shortName    ?position }
    OPTIONAL { ?player onto:hasNationality ?nat .
               ?nat    onto:name          ?nationality }
    OPTIONAL { ?player onto:jerseyNumber ?jersey }
}
ORDER BY ?position ?playerName
""",
    },

    "top_scorers": {
        "description": "Top goal scorers in the dataset (all matches)",
        "query": """\
SELECT ?playerName ?clubName (COUNT(?goal) AS ?goals)
WHERE {
    ?goal a onto:Goal ;
          onto:scoredBy   ?player ;
          onto:scoredForTeam ?club .
    ?player onto:name     ?playerName .
    ?club   onto:name     ?clubName .
}
GROUP BY ?playerName ?clubName
ORDER BY DESC(?goals)
LIMIT 10
""",
    },

    "match_results": {
        "description": "All match results with score and date",
        "query": """\
SELECT ?homeClub ?awayClub ?homeScore ?awayScore ?matchDate ?week
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
ORDER BY ?matchDate
""",
    },

    "high_value_transfers": {
        "description": "Transfers with fee > 50 million EUR",
        "query": """\
SELECT ?playerName ?fromURI ?toClub ?fee ?date
WHERE {
    ?transfer a onto:Transfer ;
              onto:transferredPlayer ?player ;
              onto:fromClub          ?from ;
              onto:toClub            ?to ;
              onto:transferFee       ?fee .
    FILTER (?fee > 50)
    ?player onto:name ?playerName .
    BIND(STR(?from) AS ?fromURI)
    ?to     onto:name ?toClub .
    OPTIONAL { ?transfer onto:transferDate ?date }
}
ORDER BY DESC(?fee)
""",
    },

    "stadiums": {
        "description": "Stadiums with capacity and GeoNames city link",
        "query": """\
SELECT ?stadiumName ?city ?capacity ?geoCity
WHERE {
    ?stadium a onto:Stadium ;
             onto:name     ?stadiumName ;
             onto:city     ?city ;
             onto:capacity ?capacity .
    OPTIONAL { ?stadium schema:location ?geoCity }
}
ORDER BY DESC(?capacity)
""",
    },

    "external_links": {
        "description": "Show DBpedia owl:sameAs links for clubs",
        "query": """\
SELECT ?clubName ?dbpediaURI
WHERE {
    ?club a onto:FootballClub ;
          onto:name  ?clubName ;
          owl:sameAs ?dbpediaURI .
    FILTER(CONTAINS(STR(?dbpediaURI), "dbpedia.org"))
}
ORDER BY ?clubName
""",
    },

    "wikidata_players": {
        "description": "Players with Wikidata links",
        "query": """\
SELECT ?playerName ?wikidataURI
WHERE {
    ?player a onto:Player ;
            onto:name  ?playerName ;
            owl:sameAs ?wikidataURI .
    FILTER(CONTAINS(STR(?wikidataURI), "wikidata.org"))
}
ORDER BY ?playerName
LIMIT 15
""",
    },

    "matches_per_club": {
        "description": "Number of home and away matches per club",
        "query": """\
SELECT ?clubName
       (COUNT(DISTINCT ?homeMatch) AS ?homeMatches)
       (COUNT(DISTINCT ?awayMatch) AS ?awayMatches)
WHERE {
    ?club a onto:FootballClub ;
          onto:name ?clubName .
    OPTIONAL { ?homeMatch onto:homeTeam ?club }
    OPTIONAL { ?awayMatch onto:awayTeam ?club }
}
GROUP BY ?clubName
ORDER BY ?clubName
""",
    },

    "goals_per_match": {
        "description": "Total goals per match (home vs away format)",
        "query": """\
SELECT ?homeClub ?awayClub ?matchDate ?homeScore ?awayScore ?totalGoals
WHERE {
    ?match a onto:Match ;
           onto:homeTeam  ?home ;
           onto:awayTeam  ?away ;
           onto:homeScore ?homeScore ;
           onto:awayScore ?awayScore ;
           onto:matchDate ?matchDate .
    ?home onto:shortName ?homeClub .
    ?away onto:shortName ?awayClub .
    BIND((?homeScore + ?awayScore) AS ?totalGoals)
}
ORDER BY DESC(?totalGoals)
""",
    },

    "managers": {
        "description": "All managers with club and nationality",
        "query": """\
SELECT ?managerName ?clubName ?nationality
WHERE {
    ?manager a onto:Manager ;
             onto:name    ?managerName ;
             onto:country ?nationality .
    ?club    a onto:FootballClub ;
             onto:name      ?clubName ;
             onto:managedBy ?manager .
}
ORDER BY ?managerName
""",
    },

    "arsenal_goals_detail": {
        "description": "All goals scored by Arsenal players with match and minute",
        "query": """\
SELECT ?playerName ?homeClub ?awayClub ?minute ?isPenalty ?matchDate
WHERE {
    ?goal a onto:Goal ;
          onto:scoredBy       ?player ;
          onto:scoredForTeam  <http://semantic-football.org/data/club/arsenal> ;
          onto:scoredInMatch  ?match ;
          onto:goalMinute     ?minute ;
          onto:isPenalty      ?isPenalty .
    ?player onto:name         ?playerName .
    ?match  onto:homeTeam     ?home ;
            onto:awayTeam     ?away ;
            onto:matchDate    ?matchDate .
    ?home   onto:shortName    ?homeClub .
    ?away   onto:shortName    ?awayClub .
}
ORDER BY ?matchDate ?minute
""",
    },

    "describe_haaland": {
        "description": "DESCRIBE Erling Haaland (all RDF triples about him)",
        "query": "DESCRIBE <http://semantic-football.org/data/player/erling_haaland>",
    },

    "count_triples": {
        "description": "Count total triples by entity type",
        "query": """\
SELECT ?type (COUNT(?entity) AS ?count)
WHERE {
    ?entity a ?type .
    FILTER(STRSTARTS(STR(?type), "http://semantic-football.org/ontology#"))
}
GROUP BY ?type
ORDER BY DESC(?count)
""",
    },
}


# ─────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────

def shorten_uri(uri_str: str, bindings: dict) -> str:
    """Replace known namespace prefixes in a URI string for display."""
    PREFIXES = [
        ("http://semantic-football.org/data/",       "data:"),
        ("http://semantic-football.org/ontology#",   "onto:"),
        ("http://www.wikidata.org/entity/",          "wd:"),
        ("http://dbpedia.org/resource/",             "dbr:"),
        ("https://sws.geonames.org/",                "geo:"),
        ("https://schema.org/",                      "schema:"),
        ("http://www.w3.org/2002/07/owl#",           "owl:"),
        ("http://www.w3.org/1999/02/22-rdf-syntax-ns#", "rdf:"),
        ("http://xmlns.com/foaf/0.1/",               "foaf:"),
    ]
    for long, short in PREFIXES:
        if uri_str.startswith(long):
            return short + uri_str[len(long):]
    return uri_str


def format_value(val) -> str:
    from rdflib import URIRef, Literal, BNode
    if isinstance(val, URIRef):
        return shorten_uri(str(val), {})
    elif isinstance(val, Literal):
        s = str(val)
        return s[:80] + "…" if len(s) > 80 else s
    elif isinstance(val, BNode):
        return f"_:{val}"
    return str(val)


def print_table(results):
    """Print SPARQL SELECT results as an ASCII table."""
    vars_ = [str(v) for v in results.vars]
    rows  = [[format_value(row[v]) for v in results.vars] for row in results]

    if not rows:
        print("  (no results)")
        return

    # column widths
    col_w = [len(h) for h in vars_]
    for row in rows:
        for i, cell in enumerate(row):
            col_w[i] = max(col_w[i], len(cell))

    sep = "+" + "+".join("-" * (w + 2) for w in col_w) + "+"
    header = "|" + "|".join(f" {h:<{col_w[i]}} " for i, h in enumerate(vars_)) + "|"

    print(sep)
    print(header)
    print(sep)
    for row in rows:
        line = "|" + "|".join(f" {cell:<{col_w[i]}} " for i, cell in enumerate(row)) + "|"
        print(line)
    print(sep)
    print(f"  {len(rows)} row(s)")


def print_describe(results):
    """Print DESCRIBE / CONSTRUCT results as Turtle-like triples."""
    g = results.graph
    count = 0
    for s, p, o in sorted(g, key=lambda t: (str(t[0]), str(t[1]))):
        print(f"  {format_value(s)}")
        print(f"      {format_value(p)}")
        print(f"          {format_value(o)}")
        count += 1
    print(f"\n  {count} triple(s)")


def run_query(g: ConjunctiveGraph, raw_query: str):
    full_query = PREFIX_BLOCK + "\n" + raw_query.strip()
    try:
        result = g.query(full_query)
        qtype  = result.type

        if qtype == "SELECT":
            print_table(result)
        elif qtype in ("DESCRIBE", "CONSTRUCT"):
            print_describe(result)
        elif qtype == "ASK":
            print(f"  Result: {result.askAnswer}")
        else:
            print(f"  Query type '{qtype}' returned without error.")
    except Exception as e:
        print(f"  ERROR: {e}")


# ─────────────────────────────────────────────────────────────
#  REPL
# ─────────────────────────────────────────────────────────────

HELP_TEXT = """
Commands
--------
  :help              Show this help message
  :examples          List all named example queries
  :run <name>        Execute a named example query
  :show <name>       Print the SPARQL text of a named example query
  :prefixes          Print the auto-prepended PREFIX block
  :count             Show total triple count in the graph
  :quit  / :exit     Exit the terminal

Ad-hoc queries
--------------
  Type (or paste) any SPARQL query and press Enter twice (blank line) to run.
  The PREFIX block is added automatically — no need to type prefixes.

Multi-line input
----------------
  Keep typing lines. A blank line submits the query.
"""


def repl(g: ConjunctiveGraph):
    print("\n" + "=" * 60)
    print(" Football Linked Data — SPARQL Terminal")
    print("=" * 60)
    print(f" Dataset loaded: {len(g)} triples")
    print(" Type  :help  for available commands.\n")

    buf = []

    while True:
        try:
            prompt = "SPARQL> " if not buf else "     …  "
            line   = input(prompt)
        except (EOFError, KeyboardInterrupt):
            print("\nBye!")
            break

        # ── Commands ────────────────────────────────────────────
        stripped = line.strip()

        if stripped in (":quit", ":exit", ":q"):
            print("Bye!")
            break

        elif stripped == ":help":
            print(HELP_TEXT)
            buf = []

        elif stripped == ":prefixes":
            print(PREFIX_BLOCK)
            buf = []

        elif stripped == ":count":
            print(f"  Total triples: {len(g)}")
            buf = []

        elif stripped == ":examples":
            print("\n  Named example queries:")
            for name, info in EXAMPLE_QUERIES.items():
                print(f"    {name:<28}  {info['description']}")
            print()
            buf = []

        elif stripped.startswith(":run "):
            qname = stripped[5:].strip()
            if qname not in EXAMPLE_QUERIES:
                print(f"  Unknown example: '{qname}'. Use :examples to list them.")
            else:
                info = EXAMPLE_QUERIES[qname]
                print(f"\n  [{qname}] {info['description']}")
                print()
                run_query(g, info["query"])
            buf = []

        elif stripped.startswith(":show "):
            qname = stripped[6:].strip()
            if qname not in EXAMPLE_QUERIES:
                print(f"  Unknown example: '{qname}'.")
            else:
                print(f"\n  -- {EXAMPLE_QUERIES[qname]['description']} --")
                print(PREFIX_BLOCK + EXAMPLE_QUERIES[qname]["query"])
            buf = []

        elif stripped == "" and buf:
            # blank line after input → submit
            query = "\n".join(buf)
            buf   = []
            print()
            run_query(g, query)
            print()

        elif stripped == "" and not buf:
            pass  # ignore leading blank lines

        else:
            buf.append(line)


# ─────────────────────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Interactive SPARQL terminal for Football Linked Data"
    )
    parser.add_argument(
        "--dataset", choices=["4star", "5star"], default="5star",
        help="Which dataset to load (default: 5star)"
    )
    args = parser.parse_args()

    ttl_path = LINKED_TTL if args.dataset == "5star" else RDF_TTL
    if not ttl_path.exists():
        print(f"Dataset not found: {ttl_path}")
        print("Run scripts/transform.py (and scripts/link.py for 5star) first.")
        sys.exit(1)

    g = ConjunctiveGraph()
    # Load ontology first so class/property definitions are available
    if ONTO_TTL.exists():
        g.parse(str(ONTO_TTL), format="turtle")
    g.parse(str(ttl_path), format="turtle")

    repl(g)


if __name__ == "__main__":
    main()
