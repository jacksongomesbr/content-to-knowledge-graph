"""Agent-neutral CLI envelope. --json is opt-in; human output stays compatible."""
import argparse
from contextlib import redirect_stdout
import json
import sqlite3
import subprocess
import sys
import traceback

MACHINE = False
_RESULT_STREAM = None
_EMITTED = False


class CliError(Exception):
    def __init__(self, message, code='operation_failed', exit_code=1):
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code


class Parser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_argument('--json', action='store_true', help='Emitir resultados no protocolo JSON para agentes')
        self.add_argument('--debug', action='store_true', help='Incluir traceback de erro em stderr')

    def error(self, message):
        raise CliError(message, 'usage_error', 2)

    def exit(self, status=0, message=None):
        if status:
            raise CliError((message or 'Operação não concluída.').strip(), 'usage_error' if status == 2 else 'operation_failed', status)
        raise SystemExit(0)


def emit(data=None, human=None, status='success', error=None):
    global _EMITTED
    _EMITTED = True
    if MACHINE:
        payload = dict(schemaVersion=1, ok=status in ('success','ready','stopped'), status=status, data=data, error=error)
        print(json.dumps(payload, ensure_ascii=False, allow_nan=False, default=str), file=_RESULT_STREAM, flush=True)
    else:
        print(human if human is not None else json.dumps(data, ensure_ascii=False, indent=2, default=str), flush=True)


def _run(main):
    """Exactly one JSON result per finite command; ready/stopped events for servers."""
    global MACHINE, _RESULT_STREAM, _EMITTED
    _RESULT_STREAM = sys.stdout
    _EMITTED = False
    # Honor -- as an end-of-options delimiter for positional values.
    boundary = sys.argv.index('--') if '--' in sys.argv else len(sys.argv)
    options = sys.argv[1:boundary]
    MACHINE = '--json' in options
    debug = '--debug' in options
    sys.argv = [sys.argv[0]] + [arg for arg in options if arg not in ('--json','--debug')] + sys.argv[boundary:]
    try:
        if MACHINE:
            with redirect_stdout(sys.stderr):
                code = main() or 0
        else:
            code = main() or 0
        if MACHINE and not _EMITTED:
            emit({}, status='success' if code == 0 else 'partial' if code == 3 else 'error')
        return code
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else 1
        if MACHINE and not _EMITTED:
            emit({'help':True} if code == 0 else None, status='success' if code == 0 else 'error', error=None if code == 0 else dict(code='operation_failed', message=str(exc)))
        return code
    except KeyboardInterrupt:
        if MACHINE: emit(status='error', error=dict(code='interrupted', message='Operação interrompida.'))
        else: print('Operação interrompida.', file=sys.stderr)
        return 130
    except Exception as exc:
        code = getattr(exc, 'exit_code', 1)
        category = getattr(exc, 'code', None)
        if category is None:
            category = 'missing_dependency' if isinstance(exc, ImportError) else 'not_found' if isinstance(exc, FileNotFoundError) else 'index_error' if isinstance(exc, sqlite3.Error) else 'subprocess_failed' if isinstance(exc, subprocess.CalledProcessError) else 'invalid_data' if isinstance(exc, (ValueError, TypeError, KeyError)) else 'io_error' if isinstance(exc, OSError) else 'internal_error'
        if MACHINE: emit(status='error', error=dict(code=category, message=str(exc)))
        else: print(f'{category}: {exc}', file=sys.stderr)
        if debug: traceback.print_exc(file=sys.stderr)
        return code


def run(main):
    global MACHINE, _RESULT_STREAM, _EMITTED
    previous = (MACHINE, _RESULT_STREAM, _EMITTED, sys.argv[:])
    try:
        return _run(main)
    finally:
        MACHINE, _RESULT_STREAM, _EMITTED, sys.argv = previous
