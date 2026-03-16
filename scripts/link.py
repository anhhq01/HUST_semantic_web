#!/usr/bin/env python3
"""
link.py — Establishes links to external Linked Data datasets to achieve the
5-star Linked Data standard:

  ★★★★★  All of the above, plus link your data to other people's data to
          provide context.

Strategy
--------
1. Load the 4★ RDF graph produced by transform.py.
2. For all entities that already carry owl:sameAs to DBpedia / Wikidata URIs
   (embedded during transformation), verify / augment with additional
   cross-dataset links.
3. Add schema:sameAs, skos:exactMatch links where applicable.
4. Enrich with foaf:depiction, schema:description pulled from DBpedia SPARQL
   where the service is reachable (gracefully skipped if offline).
5. Write the enriched graph to data/linked/football_linked.ttl.

The output is the full 5★ dataset: our data + links to DBpedia, Wikidata,
schema.org, and GeoNames.
"""

import sys
import time
from pathlib import Path

from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD
from rdflib.namespace import SKOS, FOAF
try:
    from SPARQLWrapper import SPARQLWrapper, JSON
    SPARQL_AVAILABLE = True
except ImportError:
    SPARQL_AVAILABLE = False

BASE_DIR   = Path(__file__).parent.parent
RDF_DIR    = BASE_DIR / "data" / "rdf"
LINKED_DIR = BASE_DIR / "data" / "linked"
LINKED_DIR.mkdir(parents=True, exist_ok=True)

ONTO   = Namespace("http://semantic-football.org/ontology#")
DATA   = Namespace("http://semantic-football.org/data/")
SCHEMA = Namespace("https://schema.org/")
DC     = Namespace("http://purl.org/dc/elements/1.1/")
GEO    = Namespace("http://www.geonames.org/ontology#")
PROV   = Namespace("http://www.w3.org/ns/prov#")

# ── GeoNames URIs for stadium / club cities ──────────────────────────────────
CITY_GEONAMES = {
    "Manchester": "https://sws.geonames.org/2643123/",
    "London":     "https://sws.geonames.org/2643743/",
    "Liverpool":  "https://sws.geonames.org/2644210/",
    "Birmingham": "https://sws.geonames.org/2655603/",
}

# ── Additional DBpedia links not already stored in the CSV ───────────────────
#    format: (local_uri_suffix, dbpedia_URI)
EXTRA_DBPEDIA = [
    ("league/premier_league",
     "http://dbpedia.org/resource/Premier_League"),
    ("season/pl_2023_24",
     "http://dbpedia.org/resource/2023%E2%80%9324_Premier_League_season"),
    ("season/pl_2022_23",
     "http://dbpedia.org/resource/2022%E2%80%9323_Premier_League_season"),
]

# ── Wikidata URIs for nationalities ─────────────────────────────────────────
NATIONALITY_WIKIDATA = {
    "english":     "Q145",
    "norwegian":   "Q20",
    "belgian":     "Q31",
    "spanish":     "Q29",
    "portuguese":  "Q45",
    "french":      "Q142",
    "brazilian":   "Q155",
    "dutch":       "Q55",
    "uruguayan":   "Q77",
    "argentinian": "Q414",
    "italian":     "Q38",
    "egyptian":    "Q79",
    "south_korean":"Q884",
    "welsh":       "Q25",
    "jamaican":    "Q766",
    "senegalese":  "Q1041",
    "australian":  "Q408",
    "german":      "Q183",
}


def load_rdf_graph() -> Graph:
    g = Graph()
    g.bind("onto",   ONTO)
    g.bind("data",   DATA)
    g.bind("schema", SCHEMA)
    g.bind("foaf",   FOAF)
    g.bind("owl",    OWL)
    g.bind("xsd",    XSD)
    g.bind("rdfs",   RDFS)
    g.bind("dc",     DC)
    g.bind("skos",   SKOS)
    g.bind("geo",    GEO)
    g.bind("prov",   PROV)

    ttl_path = RDF_DIR / "football_data.ttl"
    if not ttl_path.exists():
        print(f"ERROR: {ttl_path} not found. Run transform.py first.")
        sys.exit(1)
    g.parse(str(ttl_path), format="turtle")
    print(f"  Loaded {len(g)} triples from 4★ graph.")
    return g


def add_schema_same_as(g: Graph):
    """
    For every owl:sameAs triple we add the equivalent schema:sameAs triple
    so the dataset is also consumable by schema.org-aware consumers
    (e.g. Google Knowledge Graph).
    """
    same_as_pairs = list(g.subject_objects(OWL.sameAs))
    added = 0
    for subj, obj in same_as_pairs:
        if (subj, SCHEMA.sameAs, obj) not in g:
            g.add((subj, SCHEMA.sameAs, obj))
            added += 1
    print(f"  Added {added} schema:sameAs triples (mirroring owl:sameAs).")


def add_skos_exact_match(g: Graph):
    """
    Add skos:exactMatch from our entities to their DBpedia counterparts,
    expressing that they refer to exactly the same real-world concept.
    """
    added = 0
    for subj, obj in list(g.subject_objects(OWL.sameAs)):
        obj_str = str(obj)
        if "dbpedia.org" in obj_str:
            if (subj, SKOS.exactMatch, obj) not in g:
                g.add((subj, SKOS.exactMatch, obj))
                added += 1
    print(f"  Added {added} skos:exactMatch triples (to DBpedia).")


def add_extra_dbpedia_links(g: Graph):
    """Add a few manually curated DBpedia links for seasons and league."""
    added = 0
    for local_suffix, dbpedia_uri in EXTRA_DBPEDIA:
        subj = DATA[local_suffix]
        obj  = URIRef(dbpedia_uri)
        if (subj, OWL.sameAs, obj) not in g:
            g.add((subj, OWL.sameAs, obj))
            g.add((subj, SKOS.exactMatch, obj))
            g.add((subj, SCHEMA.sameAs, obj))
            added += 3
    print(f"  Added {added} extra DBpedia link triples (seasons/league).")


def add_geonames_links(g: Graph):
    """
    Link stadium / club city literals to GeoNames URIs using schema:location.
    """
    added = 0
    geo_ns = Namespace("https://sws.geonames.org/")

    for entity, _, city_lit in list(g.triples((None, ONTO.city, None))):
        city_str = str(city_lit)
        if city_str in CITY_GEONAMES:
            geo_uri = URIRef(CITY_GEONAMES[city_str])
            g.add((geo_uri, RDF.type,  GEO.Feature))
            g.add((geo_uri, GEO.name,  Literal(city_str)))
            if (entity, SCHEMA.location, geo_uri) not in g:
                g.add((entity, SCHEMA.location, geo_uri))
                added += 1
    print(f"  Added {added} GeoNames city links.")


def add_nationality_wikidata_links(g: Graph):
    """Link nationality individuals to Wikidata country entities."""
    added = 0
    for nat_uri, _, name_lit in list(g.triples((None, ONTO.name, None))):
        if str(nat_uri).startswith(str(DATA) + "nationality/"):
            nat_key = str(nat_uri).split("/nationality/")[-1]
            if nat_key in NATIONALITY_WIKIDATA:
                wd = URIRef(f"http://www.wikidata.org/entity/{NATIONALITY_WIKIDATA[nat_key]}")
                if (nat_uri, OWL.sameAs, wd) not in g:
                    g.add((nat_uri, OWL.sameAs, wd))
                    g.add((nat_uri, SCHEMA.sameAs, wd))
                    added += 2
    print(f"  Added {added} nationality → Wikidata country links.")


def fetch_dbpedia_descriptions(g: Graph, limit: int = 10):
    """
    Optionally query DBpedia SPARQL to pull rdfs:comment descriptions for
    clubs and players that have a dbpedia sameAs link.
    Gracefully skipped if DBpedia is unreachable.
    """
    if not SPARQL_AVAILABLE:
        print("  SPARQLWrapper not available – skipping DBpedia enrichment.")
        return

    # Collect (local_uri, dbpedia_uri) for clubs and players
    pairs = []
    for subj, _, obj in g.triples((None, OWL.sameAs, None)):
        if "dbpedia.org/resource" in str(obj):
            subj_str = str(subj)
            if "/club/" in subj_str or "/player/" in subj_str:
                pairs.append((subj, obj))
    pairs = pairs[:limit]  # cap to avoid long delays

    sparql = SPARQLWrapper("https://dbpedia.org/sparql")
    sparql.setTimeout(10)
    added = 0
    errors = 0

    for local_uri, dbpedia_uri in pairs:
        query = f"""
        SELECT ?comment ?thumbnail WHERE {{
            OPTIONAL {{ <{dbpedia_uri}> rdfs:comment ?comment .
                        FILTER(LANG(?comment) = 'en') }}
            OPTIONAL {{ <{dbpedia_uri}> <http://dbpedia.org/ontology/thumbnail> ?thumbnail }}
        }} LIMIT 1
        """
        try:
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)
            results = sparql.query().convert()
            bindings = results.get("results", {}).get("bindings", [])
            if bindings:
                b = bindings[0]
                if "comment" in b:
                    g.add((local_uri, RDFS.comment,
                           Literal(b["comment"]["value"], lang="en")))
                    added += 1
                if "thumbnail" in b:
                    g.add((local_uri, FOAF.depiction,
                           URIRef(b["thumbnail"]["value"])))
                    added += 1
            time.sleep(0.2)  # polite crawl delay
        except Exception:
            errors += 1
            if errors >= 3:
                print("  DBpedia SPARQL unreachable – skipping remaining enrichment.")
                break

    if added:
        print(f"  Fetched {added} property values from DBpedia SPARQL.")
    else:
        print("  No DBpedia enrichment fetched (network/timeout).")


def add_provenance(g: Graph):
    """Add basic provenance metadata to the dataset."""
    ds = URIRef("http://semantic-football.org/data")
    g.add((ds, RDF.type,        PROV.Entity))
    g.add((ds, DC.title,        Literal("Football Linked Data – 5★ Dataset", lang="en")))
    g.add((ds, DC.description,  Literal(
        "Premier League 2023-24 football data (clubs, players, matches, goals, "
        "transfers) enriched with owl:sameAs links to DBpedia and Wikidata, "
        "skos:exactMatch links, GeoNames city links, and schema:sameAs triples.",
        lang="en"
    )))
    g.add((ds, DC.creator,      Literal("Semantic Web Course Project")))
    g.add((ds, DC.date,         Literal("2026-03-16", datatype=XSD.date)))
    g.add((ds, PROV.wasGeneratedBy,
           Literal("link.py — 5★ Linked Data enrichment script")))
    print("  Added provenance metadata.")


def main():
    print("=== Establishing external dataset links (5★ Linked Data) ===\n")
    g = load_rdf_graph()

    add_schema_same_as(g)
    add_skos_exact_match(g)
    add_extra_dbpedia_links(g)
    add_geonames_links(g)
    add_nationality_wikidata_links(g)
    fetch_dbpedia_descriptions(g, limit=12)
    add_provenance(g)

    out_ttl = LINKED_DIR / "football_linked.ttl"
    out_nt  = LINKED_DIR / "football_linked.nt"

    g.serialize(destination=str(out_ttl), format="turtle")
    g.serialize(destination=str(out_nt),  format="nt")

    print(f"\n✓ 5★ dataset: {len(g)} triples → {out_ttl}")
    print(f"✓ N-Triples  → {out_nt}")


if __name__ == "__main__":
    main()
