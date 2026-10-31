"""Stable identifiers for the existing HTML records, independent of Case rows."""
READING_KEYS = tuple(f'E{i:02}' for i in range(1, 31))
READING_CHOICES = [(key, key) for key in READING_KEYS]


def reading_entries():
    import re
    from pathlib import Path
    source = (Path(__file__).parent / 'templates/portal/direct_case_reading.html').read_text()
    entries = [dict(key=k, title=t, date=d, uncertain=k in ('E06', 'E10', 'E22'))
               for k, t, d in re.findall(r'id="material-(E\d+)"><h2>E\d+ · (.*?)</h2>\n<section class="reading-area"><h3>① 날짜</h3><p>(.*?)</p>', source)]
    if len(entries) != 30 or {e['key'] for e in entries} != set(READING_KEYS):
        raise ValueError('사건 메타데이터를 확인하세요.')
    return entries
