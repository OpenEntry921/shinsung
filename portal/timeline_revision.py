"""Reviewed display-number mapping; stable IDs must not be renumbered."""
BASIS = '2026년 11월 4일'
ENTRY_COUNT = 72
PREVIOUS_ENTRY_COUNT = 70
OLD_TO_REVISED = {old: old if old <= 40 else old + 1 for old in range(1, 71)}
NEW_NUMBER_KEYS = {41: 'T71', 72: 'T72'}
KEY_BY_NUMBER = {new: f'T{old:02}' for old,new in OLD_TO_REVISED.items()} | NEW_NUMBER_KEYS
TIMELINE_ORDER = tuple(KEY_BY_NUMBER[number] for number in range(1,ENTRY_COUNT+1))
