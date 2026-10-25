"""Create/reuse an isolated analysis environment and install declared requirements."""
import argparse
import importlib.util
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys
import venv

PACKAGES = ['numpy','scipy','sklearn','networkx','jsonschema','yaml','sentence_transformers','torch','pypdf','docx','bs4']


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile', choices=['core','analysis'], default='analysis')
    p.add_argument('--requirements', type=Path, help='Especificação ou lock alternativo'); p.add_argument('--venv', type=Path); p.add_argument('--check', action='store_true', help='Inspect this interpreter without installation')
    a = p.parse_args()
    if a.check:
        state = {}
        modules = ['yaml','sqlite3'] if a.profile == 'core' else PACKAGES + ['sqlite3']
        for module in modules:
            result = subprocess.run([sys.executable, '-c', f'import {module}'], capture_output=True, text=True)
            state[module] = {'ok': result.returncode == 0, 'error': result.stderr[-1500:] if result.returncode else None}
        fts = subprocess.run([sys.executable, '-c', "import sqlite3; sqlite3.connect(':memory:').execute('CREATE VIRTUAL TABLE test_fts USING fts5(text)')"], capture_output=True, text=True)
        state['sqlite_fts5'] = {'ok': fts.returncode == 0, 'error': fts.stderr[-1500:] if fts.returncode else None}
        print(json.dumps(dict(python=sys.executable, version=sys.version, profile=a.profile, packages=state), indent=2))
        return 0 if all(item['ok'] for item in state.values()) else 1
    if not a.venv: p.error('--venv é obrigatório para preparar o ambiente')
    root = a.venv.resolve()
    if root.exists() and not (root/'pyvenv.cfg').exists(): p.error('Destino existe e não é um venv; nada foi alterado.')
    if not root.exists(): venv.EnvBuilder(with_pip=True).create(root)
    python = root/('Scripts/python.exe' if sys.platform == 'win32' else 'bin/python')
    requirements = a.requirements.resolve() if a.requirements else Path(__file__).resolve().parents[1]/('references/requirements-core.txt' if a.profile == 'core' else 'references/requirements-analysis.txt')
    subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
    subprocess.run([str(python), '-m', 'pip', 'check'], check=True)
    subprocess.run([str(python), str(Path(__file__).resolve()), '--check', '--profile', a.profile], check=True)
    lock = subprocess.check_output([str(python), '-m', 'pip', 'freeze'], text=True)
    (root.parent/('requirements-core.lock.txt' if a.profile == 'core' else 'requirements-analysis.lock.txt')).write_text(lock)
    print(f'Ambiente pronto: {python}. Execute generate_embeddings.py para testar a inferência real.')
    return 0

if __name__ == '__main__': sys.exit(main())
