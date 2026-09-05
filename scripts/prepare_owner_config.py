"""Extract only the old owner's literal ID; never execute legacy source.

Run on Hermes: python3 scripts/prepare_owner_config.py /home/hermes/alfa_sync/app/tg_bot.py
Writes a separate .env.owner, leaving .env and all credentials untouched.
"""
import ast
import os
from pathlib import Path
import sys


def extract_owner(source: str) -> int:
    values = []
    for node in ast.parse(source).body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(isinstance(t, ast.Name) and t.id == 'ALLOWED_USER_ID' for t in targets):
            if not isinstance(node.value, ast.Constant) or type(node.value.value) is not int:
                raise ValueError('Owner must be an explicit integer literal in legacy source')
            values.append(node.value.value)
    if len(values) != 1 or values[0] <= 0:
        raise ValueError('Expected exactly one positive legacy owner ID')
    return values[0]


def main():
    try:
        owner = extract_owner(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
        destination = Path('.env.owner')
        content = f'TELEGRAM_ALLOWED_USER_ID={owner}\n'
        if destination.exists():
            if destination.read_text(encoding='utf-8') != content:
                raise ValueError('Existing owner configuration differs; left unchanged')
        else:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
                stream.write(content)
        print('OWNER_CONFIG_OK')
        return 0
    except (OSError, ValueError, SyntaxError, IndexError):
        print('OWNER_CONFIG_FAILED: no credentials or source printed', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
