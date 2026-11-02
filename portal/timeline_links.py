"""Reviewed cross-references only. Never move or merge legacy discussion records."""
LEGACY_RELATED = {
    'E01': ('T01',), 'E02': ('T03',), 'E03': ('T06',), 'E04': ('T07','T08'),
    'E05': (), 'E06': ('T10',), 'E07': ('T13',), 'E08': ('T13',),
    'E09': ('T15',), 'E10': ('T16','T17'), 'E11': ('T18',), 'E12': ('T20',),
    'E13': ('T21',), 'E14': ('T24',), 'E15': ('T29',), 'E16': ('T30',),
    'E17': ('T31',), 'E18': ('T33',), 'E19': ('T33',), 'E20': ('T35',),
    'E21': ('T39',), 'E22': ('T40',), 'E23': ('T43',), 'E24': ('T46','T47'),
    'E25': ('T48',), 'E26': (), 'E27': ('T59',), 'E28': ('T60',),
    'E29': ('T60',), 'E30': ('T62','T63'),
}
# Source code -> existing Document ID, assigned only after manual source/redaction review.
# Empty means no authenticated reading copy has been explicitly connected.
SOURCE_DOCUMENT_IDS = {}
