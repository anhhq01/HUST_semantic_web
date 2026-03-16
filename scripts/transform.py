#!/usr/bin/env python3
"""
transform.py — Converts raw CSV data into RDF (Turtle) following the 4-star
Linked Data standard:
  ★★★★  URIs for all entities, machine-readable RDF, open format, use open standards.

Output: data/rdf/football_data.ttl
"""

import csv
import os
from pathlib import Path
from rdflib import Graph, Namespace, URIRef, Literal, RDF, RDFS, OWL, XSD

# ─────────────────────────────────────────────────────────────
#  Namespaces
# ─────────────────────────────────────────────────────────────
ONTO  = Namespace("http://semantic-football.org/ontology#")
DATA  = Namespace("http://semantic-football.org/data/")
SCHEMA = Namespace("https://schema.org/")
FOAF  = Namespace("http://xmlns.com/foaf/0.1/")
DC    = Namespace("http://purl.org/dc/elements/1.1/")

BASE_DIR = Path(__file__).parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"
RDF_DIR  = BASE_DIR / "data" / "rdf"
RDF_DIR.mkdir(parents=True, exist_ok=True)

# ─────────────────────────────────────────────────────────────
#  Graph initialisation
# ─────────────────────────────────────────────────────────────
def create_graph() -> Graph:
    g = Graph()
    g.bind("onto",   ONTO)
    g.bind("data",   DATA)
    g.bind("schema", SCHEMA)
    g.bind("foaf",   FOAF)
    g.bind("owl",    OWL)
    g.bind("xsd",    XSD)
    g.bind("rdfs",   RDFS)
    g.bind("dc",     DC)
    # Import ontology
    g.add((URIRef("http://semantic-football.org/data"),
           OWL.imports,
           URIRef("http://semantic-football.org/ontology")))
    return g


def read_csv(filename: str) -> list[dict]:
    path = RAW_DIR / filename
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def uri(path: str) -> URIRef:
    return DATA[path]


# ─────────────────────────────────────────────────────────────
#  Loaders
# ─────────────────────────────────────────────────────────────

def load_leagues(g: Graph):
    for row in read_csv("leagues.csv"):
        league = uri(f"league/{row['league_id']}")
        g.add((league, RDF.type,           ONTO.League))
        g.add((league, ONTO.name,          Literal(row["name"], lang="en")))
        g.add((league, ONTO.shortName,     Literal(row["short_name"])))
        g.add((league, ONTO.country,       Literal(row["country"])))
        g.add((league, DC.identifier,      Literal(row["league_id"])))
        if row.get("founded"):
            g.add((league, ONTO.founded,   Literal(int(row["founded"]), datatype=XSD.integer)))
        if row.get("wikidata_id"):
            g.add((league, OWL.sameAs,
                   URIRef(f"http://www.wikidata.org/entity/{row['wikidata_id']}")))
        if row.get("dbpedia_uri"):
            g.add((league, OWL.sameAs, URIRef(row["dbpedia_uri"])))
    print(f"  Loaded {len(read_csv('leagues.csv'))} leagues")


def load_seasons(g: Graph):
    for row in read_csv("seasons.csv"):
        season = uri(f"season/{row['season_id']}")
        g.add((season, RDF.type,          ONTO.Season))
        g.add((season, ONTO.seasonLabel,  Literal(row["label"])))
        g.add((season, DC.identifier,     Literal(row["season_id"])))
        g.add((season, ONTO.name,         Literal(row["label"])))
        # link to league
        league = uri(f"league/{row['league_id']}")
        g.add((league, ONTO.hasSeason,    season))
    print(f"  Loaded {len(read_csv('seasons.csv'))} seasons")


def load_stadiums(g: Graph):
    for row in read_csv("stadiums.csv"):
        stadium = uri(f"stadium/{row['stadium_id']}")
        g.add((stadium, RDF.type,         ONTO.Stadium))
        g.add((stadium, ONTO.name,        Literal(row["name"], lang="en")))
        g.add((stadium, ONTO.city,        Literal(row["city"])))
        g.add((stadium, ONTO.country,     Literal(row["country"])))
        g.add((stadium, DC.identifier,    Literal(row["stadium_id"])))
        if row.get("capacity"):
            g.add((stadium, ONTO.capacity,
                   Literal(int(row["capacity"]), datatype=XSD.integer)))
        if row.get("opened"):
            g.add((stadium, ONTO.founded,
                   Literal(int(row["opened"]), datatype=XSD.integer)))
        if row.get("wikidata_id"):
            g.add((stadium, OWL.sameAs,
                   URIRef(f"http://www.wikidata.org/entity/{row['wikidata_id']}")))
        if row.get("dbpedia_uri"):
            g.add((stadium, OWL.sameAs, URIRef(row["dbpedia_uri"])))
    print(f"  Loaded {len(read_csv('stadiums.csv'))} stadiums")


def load_clubs(g: Graph):
    for row in read_csv("clubs.csv"):
        club = uri(f"club/{row['club_id']}")
        g.add((club, RDF.type,           ONTO.FootballClub))
        g.add((club, ONTO.name,          Literal(row["name"], lang="en")))
        g.add((club, ONTO.shortName,     Literal(row["short_name"])))
        g.add((club, ONTO.city,          Literal(row["city"])))
        g.add((club, ONTO.country,       Literal(row["country"])))
        g.add((club, DC.identifier,      Literal(row["club_id"])))
        if row.get("founded"):
            g.add((club, ONTO.founded,
                   Literal(int(row["founded"]), datatype=XSD.integer)))
        # stadium link
        if row.get("stadium_id"):
            g.add((club, ONTO.hasStadium, uri(f"stadium/{row['stadium_id']}")))
        # league (Premier League hard-coded as only league here)
        g.add((club, ONTO.participatesIn, uri("league/premier_league")))
        # external URIs
        if row.get("wikidata_id"):
            g.add((club, OWL.sameAs,
                   URIRef(f"http://www.wikidata.org/entity/{row['wikidata_id']}")))
        if row.get("dbpedia_uri"):
            g.add((club, OWL.sameAs, URIRef(row["dbpedia_uri"])))
    print(f"  Loaded {len(read_csv('clubs.csv'))} clubs")


def load_managers(g: Graph):
    position_map = {
        "Goalkeeper": ONTO.Goalkeeper,
        "Defender":   ONTO.Defender,
        "Midfielder":  ONTO.Midfielder,
        "Forward":    ONTO.Forward,
    }
    for row in read_csv("managers.csv"):
        manager = uri(f"manager/{row['manager_id']}")
        g.add((manager, RDF.type,          ONTO.Manager))
        g.add((manager, FOAF.name,         Literal(row["name"])))
        g.add((manager, ONTO.name,         Literal(row["name"])))
        g.add((manager, ONTO.country,      Literal(row["nationality"])))
        g.add((manager, DC.identifier,     Literal(row["manager_id"])))
        if row.get("date_of_birth"):
            g.add((manager, ONTO.dateOfBirth,
                   Literal(row["date_of_birth"], datatype=XSD.date)))
        # link club -> manager
        if row.get("club_id"):
            club = uri(f"club/{row['club_id']}")
            g.add((club, ONTO.managedBy, manager))
        if row.get("wikidata_id"):
            g.add((manager, OWL.sameAs,
                   URIRef(f"http://www.wikidata.org/entity/{row['wikidata_id']}")))
        if row.get("dbpedia_uri"):
            g.add((manager, OWL.sameAs, URIRef(row["dbpedia_uri"])))
    print(f"  Loaded {len(read_csv('managers.csv'))} managers")


def load_players(g: Graph):
    position_map = {
        "Goalkeeper": ONTO.Goalkeeper,
        "Defender":   ONTO.Defender,
        "Midfielder":  ONTO.Midfielder,
        "Forward":    ONTO.Forward,
    }
    for row in read_csv("players.csv"):
        player = uri(f"player/{row['player_id']}")
        g.add((player, RDF.type,          ONTO.Player))
        g.add((player, FOAF.name,         Literal(row["name"])))
        g.add((player, ONTO.name,         Literal(row["name"])))
        g.add((player, DC.identifier,     Literal(row["player_id"])))
        if row.get("date_of_birth"):
            g.add((player, ONTO.dateOfBirth,
                   Literal(row["date_of_birth"], datatype=XSD.date)))
        if row.get("nationality"):
            nat_id = row["nationality"].lower().replace(" ", "_")
            nat_uri = uri(f"nationality/{nat_id}")
            g.add((nat_uri, RDF.type,     ONTO.Nationality))
            g.add((nat_uri, ONTO.name,    Literal(row["nationality"])))
            g.add((player, ONTO.hasNationality, nat_uri))
        pos_label = row.get("position", "")
        if pos_label in position_map:
            g.add((player, ONTO.hasPosition, position_map[pos_label]))
        if row.get("jersey_number"):
            g.add((player, ONTO.jerseyNumber,
                   Literal(int(row["jersey_number"]), datatype=XSD.integer)))
        if row.get("height_cm"):
            g.add((player, ONTO.height,
                   Literal(float(row["height_cm"]), datatype=XSD.decimal)))
        if row.get("market_value_m"):
            g.add((player, ONTO.marketValue,
                   Literal(float(row["market_value_m"]), datatype=XSD.decimal)))
        if row.get("club_id"):
            g.add((player, ONTO.playsFor, uri(f"club/{row['club_id']}")))
        if row.get("wikidata_id"):
            g.add((player, OWL.sameAs,
                   URIRef(f"http://www.wikidata.org/entity/{row['wikidata_id']}")))
        if row.get("dbpedia_uri"):
            g.add((player, OWL.sameAs, URIRef(row["dbpedia_uri"])))
    print(f"  Loaded {len(read_csv('players.csv'))} players")


def load_matches(g: Graph):
    rows = read_csv("matches.csv")
    for row in rows:
        match = uri(f"match/{row['match_id']}")
        g.add((match, RDF.type,           ONTO.Match))
        g.add((match, DC.identifier,      Literal(row["match_id"])))
        g.add((match, ONTO.homeTeam,      uri(f"club/{row['home_team']}")))
        g.add((match, ONTO.awayTeam,      uri(f"club/{row['away_team']}")))
        g.add((match, ONTO.matchDate,
               Literal(row["match_date"], datatype=XSD.date)))
        g.add((match, ONTO.matchWeek,
               Literal(int(row["match_week"]), datatype=XSD.integer)))
        home_score = int(row["home_score"])
        away_score = int(row["away_score"])
        g.add((match, ONTO.homeScore,
               Literal(home_score, datatype=XSD.integer)))
        g.add((match, ONTO.awayScore,
               Literal(away_score, datatype=XSD.integer)))
        # derived: winner
        if home_score > away_score:
            g.add((match, ONTO.wonBy, uri(f"club/{row['home_team']}")))
        elif away_score > home_score:
            g.add((match, ONTO.wonBy, uri(f"club/{row['away_team']}")))
        # else draw — no wonBy triple
        g.add((match, ONTO.partOfLeague,  uri(f"league/{row['league_id']}")))
        g.add((match, ONTO.partOfSeason,  uri(f"season/{row['season_id']}")))
        # human-readable label
        g.add((match, RDFS.label,
               Literal(f"{row['home_team']} vs {row['away_team']} ({row['match_date']})")))
    print(f"  Loaded {len(rows)} matches")


def load_goals(g: Graph):
    rows = read_csv("goals.csv")
    for row in rows:
        goal = uri(f"goal/{row['goal_id']}")
        g.add((goal, RDF.type,              ONTO.Goal))
        g.add((goal, DC.identifier,         Literal(row["goal_id"])))
        g.add((goal, ONTO.scoredInMatch,    uri(f"match/{row['match_id']}")))
        g.add((goal, ONTO.scoredForTeam,    uri(f"club/{row['team_id']}")))
        g.add((goal, ONTO.goalMinute,
               Literal(int(row["minute"]), datatype=XSD.integer)))
        g.add((goal, ONTO.isPenalty,
               Literal(row["is_penalty"].lower() == "true", datatype=XSD.boolean)))
        g.add((goal, ONTO.isOwnGoal,
               Literal(row["is_own_goal"].lower() == "true", datatype=XSD.boolean)))
        if row.get("scorer_id"):
            g.add((goal, ONTO.scoredBy,     uri(f"player/{row['scorer_id']}")))
    print(f"  Loaded {len(rows)} goals")


def load_transfers(g: Graph):
    rows = read_csv("transfers.csv")
    for row in rows:
        transfer = uri(f"transfer/{row['transfer_id']}")
        g.add((transfer, RDF.type,               ONTO.Transfer))
        g.add((transfer, DC.identifier,          Literal(row["transfer_id"])))
        g.add((transfer, ONTO.transferredPlayer, uri(f"player/{row['player_id']}")))
        g.add((transfer, ONTO.fromClub,          uri(f"club/{row['from_club']}")))
        g.add((transfer, ONTO.toClub,            uri(f"club/{row['to_club']}")))
        if row.get("transfer_date"):
            g.add((transfer, ONTO.transferDate,
                   Literal(row["transfer_date"], datatype=XSD.date)))
        if row.get("fee_million_eur"):
            g.add((transfer, ONTO.transferFee,
                   Literal(float(row["fee_million_eur"]), datatype=XSD.decimal)))
        if row.get("season_id"):
            g.add((transfer, ONTO.inSeason, uri(f"season/{row['season_id']}")))
    print(f"  Loaded {len(rows)} transfers")


# ─────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────

def main():
    print("=== Transforming raw CSV data to RDF (4★ Linked Data) ===\n")
    g = create_graph()

    load_leagues(g)
    load_seasons(g)
    load_stadiums(g)
    load_clubs(g)
    load_managers(g)
    load_players(g)
    load_matches(g)
    load_goals(g)
    load_transfers(g)

    output_path = RDF_DIR / "football_data.ttl"
    g.serialize(destination=str(output_path), format="turtle")
    print(f"\n✓ Serialised {len(g)} triples → {output_path}")

    # Also produce N-Triples for maximum interoperability
    nt_path = RDF_DIR / "football_data.nt"
    g.serialize(destination=str(nt_path), format="nt")
    print(f"✓ Serialised N-Triples → {nt_path}")


if __name__ == "__main__":
    main()
