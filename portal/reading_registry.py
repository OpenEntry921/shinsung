"""Stable identifiers for the existing HTML records, independent of Case rows."""
READING_KEYS = tuple(f'E{i:02}' for i in range(1, 31))
READING_CHOICES = [(key, key) for key in READING_KEYS]
