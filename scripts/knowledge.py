"""Import, validate, index, search and traverse a canonical Markdown knowledge base."""
import argparse
import json
from pathlib import Path
import sqlite3
from knowledge_store import build, import_graph, read_store, search, neighbors, recover


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    migrate = commands.add_parser('import-json'); migrate.add_argument('graph', type=Path); migrate.add_argument('--output', type=Path, required=True)
    for name in ('validate', 'build', 'search', 'neighbors', 'recover'):
        command = commands.add_parser(name); command.add_argument('root', type=Path)
        if name == 'search':
            command.add_argument('query'); command.add_argument('--kind', choices=['entity','relation','source','bibliography']); command.add_argument('--limit', type=int, default=20)
        if name == 'neighbors':
            command.add_argument('id'); command.add_argument('--depth', type=int, default=1); command.add_argument('--direction', choices=['both','in','out'], default='both')
    args = parser.parse_args()
    try:
        if args.command == 'import-json': result = {'root': str(import_graph(args.graph, args.output))}
        elif args.command == 'validate':
            root, _, records, _ = read_store(args.root); result = {'root': str(root), 'records': len(records), 'valid': True}
        elif args.command == 'build': result = build(args.root)
        elif args.command == 'search': result = search(args.root, args.query, args.kind, args.limit)
        elif args.command == 'neighbors': result = neighbors(args.root, args.id, args.depth, args.direction)
        else: recover(args.root); result = {'recovered': True}
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, sqlite3.Error, TypeError) as exc:
        parser.exit(1, f'Base de conhecimento: {exc}\n')

if __name__ == '__main__': main()
