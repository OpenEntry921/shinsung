"""Safe deployment diagnostics without titles, excerpts, paths, keys or exception traces."""
import json
from django.core.management.base import BaseCommand
from portal.fixed_reading import load_reading, ReadingUnavailable


class Command(BaseCommand):
    help = 'Validate encrypted reading and runtime key; prints only status and counts.'

    def handle(self, *args, **options):
        try:
            body = load_reading()
        except ReadingUnavailable as exc:
            self.stdout.write(json.dumps({'ready': False, 'reason': exc.code}))
            raise SystemExit(1)
        self.stdout.write(json.dumps({'ready': True, 'cases': len(body['entries']),
                                    'dated': len(body['dated_entries']),
                                    'uncertain': len(body['uncertain_entries']),
                                    'database_persistence_verified': False}))
