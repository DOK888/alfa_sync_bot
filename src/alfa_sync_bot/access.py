"""Owner-only access; configuration never comes from a Telegram update."""
import os
import re


def owner_id() -> int:
    value = os.environ.get('TELEGRAM_ALLOWED_USER_ID', '').strip()
    if not re.fullmatch(r'[1-9][0-9]*', value):
        raise ValueError('TELEGRAM_ALLOWED_USER_ID must be a positive integer')
    return int(value)


def is_owner_message(message: object, owner: int) -> bool:
    if not isinstance(message, dict):
        return False
    chat, sender = message.get('chat'), message.get('from')
    return (
        isinstance(chat, dict) and isinstance(sender, dict)
        and chat.get('type') == 'private'
        and type(chat.get('id')) is int and chat['id'] == owner
        and type(sender.get('id')) is int and sender['id'] == owner
    )
