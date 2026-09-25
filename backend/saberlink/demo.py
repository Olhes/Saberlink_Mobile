"""Quick manual test of the live pipeline from the command line.

Usage:
    python -m saberlink.demo NEED-005
    python -m saberlink.demo NEED-013 --top 8

    # o describí una necesidad en texto libre, sin ID — se trata como
    # necesidad temporal (igual que un PDF subido vía Docling), nunca se
    # persiste en institutional_needs.csv:
    python -m saberlink.demo --title "Detección temprana de plagio" --text "Necesitamos identificar similitud entre entregas de estudiantes..."

Prints a human-readable view of run_query()'s output: ranked connections,
the top result's explanation + evidence, and any opportunities generated.
Run it a few times in the same interactive session (or use the notebook,
once built) to see later calls answer in ~1-2s instead of the ~20s the
first call pays for loading the embedding model and indices.
"""

from __future__ import annotations

import argparse
import sys

from saberlink import pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live SaberLink query and print the results.")
    parser.add_argument("entity_id", nargs="?", default=None, help="e.g. NEED-001, NEED-013, PRJ-001, INV-001")
    parser.add_argument("--text", default=None, help="descripción en texto libre, en vez de un ID existente")
    parser.add_argument("--title", default=None, help="título corto para --text (si no se da, se usa --text truncado)")
    parser.add_argument("--context", default=None, help="contexto opcional para --text")
    parser.add_argument("--impact", default=None, help="impacto esperado opcional para --text")
    parser.add_argument("--top", type=int, default=5, help="how many connections to show (default 5)")
    args = parser.parse_args()

    if not args.entity_id and not args.text:
        parser.error("hay que dar un entity_id o --text")

    if args.text:
        raw_text_profile = {
            "title": args.title or args.text[:80],
            "description": args.text,
            "context": args.context,
            "expected_impact": args.impact,
        }
        out = pipeline.run_query(raw_text_profile=raw_text_profile, top_k=args.top)
    else:
        out = pipeline.run_query(entity_id=args.entity_id, top_k=args.top)

    print(f"\nCONSULTA: {out['source']['id']} ({out['source']['type']})")
    print(f"tiempo: {out['meta']['elapsed_seconds']}s | candidatos evaluados: {out['meta']['total_candidates_scored']}\n")

    print(f"TOP {len(out['results'])} CONEXIONES:")
    for i, r in enumerate(out["results"], 1):
        rel = r["relevance"]
        print(f"  {i}. {r['target']['type']} {r['target']['id']}  score={rel['score']:.2f} ({rel['label']})")

    if out["results"]:
        top = out["results"][0]
        print(f"\nEXPLICACION DEL #1 ({top['target']['id']}):")
        print(" ", top["explanation"])
        print("\nEVIDENCIA:")
        for ev in top["evidence"]:
            snippet = ev["snippet"][:150]
            print(f"   - {ev['file']} / {ev['id']} / {ev['field']}: {snippet}")

    print("\nOPORTUNIDADES:")
    if not out["opportunities"]:
        print("  (ninguna disparó para esta consulta)")
    for o in out["opportunities"]:
        print(f"  [{o['type']}] {o['opportunity']}")
        print(f"    razón: {o['reason']}  | prioridad: {o['priority']}")
    print()


if __name__ == "__main__":
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
