"""Validate graph and optional layout; exits nonzero on invalid artifacts."""
from cli_common import Parser, emit, run
import argparse
import json
from graph_tools import load_graph, check_layout


def main():
    p = Parser(description=__doc__); p.add_argument('graph'); p.add_argument('--layout'); args = p.parse_args()
    try:
        graph, raw = load_graph(args.graph)
        if args.layout: check_layout(json.load(open(args.layout)), graph, raw)
    except (ValueError, OSError, TypeError) as exc:
        p.exit(1, f'Inválido: {exc}\n')
    emit(dict(valid=True, nodes=len(graph["nodes"]), edges=len(graph["edges"])), human=f"OK: {len(graph['nodes'])} entidades, {len(graph['edges'])} relações.")

if __name__ == '__main__': raise SystemExit(run(main))
