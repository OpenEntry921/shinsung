"""Read reviewed text from private server storage, never from case tables."""
import datetime
import json
import re
from pathlib import Path
from django.conf import settings


class ReadingUnavailable(Exception):
    pass


def reading_path():
    return Path(settings.MEDIA_ROOT) / 'case-reading.body'


def load_reading():
    path = reading_path()
    if not path.exists():
        return None
    # The body must not be deployed as a public asset or shipped in a public checkout.
    resolved = path.resolve()
    base = settings.BASE_DIR.resolve()
    if base == resolved or base in resolved.parents or path.is_symlink():
        raise ReadingUnavailable()
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError()
        with path.open(encoding='utf-8') as stream:
            body = json.load(stream)
        if body['version'] != 1 or body['reviewed'] is not True:
            raise ValueError()
        if not all(isinstance(body[n], str) for n in ('basis_on', 'source_title', 'source_filename')):
            raise ValueError()
        datetime.date.fromisoformat(body['basis_on'])
        entries = body['entries']
        if not entries or len(entries) > 500:
            raise ValueError()
        seen = set()
        aliases = set()
        for entry in entries:
            key = entry['key']
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', key) or key in seen:
                raise ValueError()
            seen.add(key)
            # Partial dates are preserved as labels; ordering metadata is not an occurrence date.
            order = entry['order']
            if order is not None and (len(order) != 3 or any(type(n) is not int for n in order)):
                raise ValueError()
            if order is not None and not (1 <= order[0] <= 9999 and 0 <= order[1] <= 12 and 0 <= order[2] <= 31):
                raise ValueError()
            for name in ('title', 'date_label', 'source', 'overview', 'ordering_note', 'issues', 'needed', 'responses'):
                if not isinstance(entry[name], str):
                    raise ValueError()
            for alias in entry.get('legacy_ids', []):
                if type(alias) is not int or alias <= 0 or alias in aliases:
                    raise ValueError()
                aliases.add(alias)
            for statement in entry['statements']:
                if statement['kind'] not in ('unknown', 'claim', 'opinion'):
                    raise ValueError()
                if statement['presentation'] not in ('summary', 'quotation', 'redacted_quotation'):
                    raise ValueError()
                if not all(isinstance(statement[n], str) for n in ('text', 'source')):
                    raise ValueError()
            for rule in entry['rules']:
                if not all(isinstance(rule[n], str) for n in ('citation', 'description', 'source', 'relevance')):
                    raise ValueError()
        body['dated_entries'] = sorted((e for e in entries if e['order'] is not None), key=lambda e: (*e['order'], e['key']))
        body['uncertain_entries'] = [e for e in entries if e['order'] is None]
        return body
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        # Never include a private path or excerpt in errors/logs.
        raise ReadingUnavailable() from None
