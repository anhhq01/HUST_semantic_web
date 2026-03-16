#!/usr/bin/env python3
"""
run_all.py — One-shot pipeline that executes all steps of the assignment:

  Step 1 — transform.py  →  Generates 4★ RDF data (data/rdf/)
  Step 2 — link.py       →  Generates 5★ linked data (data/linked/)
  Step 3 — sparql_terminal.py  →  Launches interactive SPARQL terminal
"""
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent

def run(script: str, *args):
    cmd = [sys.executable, str(BASE_DIR / script)] + list(args)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"\nERROR: {script} failed with code {result.returncode}")
        sys.exit(result.returncode)

print("╔══════════════════════════════════════════════════════════╗")
print("║   Football Semantic Web — Full Pipeline                  ║")
print("╚══════════════════════════════════════════════════════════╝\n")

print("── Step 1: Transform raw CSV → 4★ RDF ─────────────────────")
run("transform.py")

print("\n── Step 2: Add external links → 5★ Linked Data ────────────")
run("link.py")

print("\n── Step 3: Launching SPARQL terminal ───────────────────────")
run("sparql_terminal.py")
