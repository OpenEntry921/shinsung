"""Only explicitly reviewed source-code mappings may expose existing reading copies."""
from django.db.models import Q
from collections import Counter
from .models import Document, Case
from .timeline_links import SOURCE_DOCUMENT_IDS


def document_links(codes):
    counts=Counter(SOURCE_DOCUMENT_IDS.values())
    selected={code:SOURCE_DOCUMENT_IDS[code] for code in codes if code in SOURCE_DOCUMENT_IDS and counts[SOURCE_DOCUMENT_IDS[code]]==1}
    if not selected:return {}
    documents=Document.objects.filter(pk__in=selected.values(),internal_memo=False,state='published',redaction_checked=True).exclude(reading='')
    visible_cases=Case.objects.filter(state='published')
    documents=documents.filter(Q(case__in=visible_cases)|Q(case_links__case__in=visible_cases)).distinct()
    by_id={document.pk:document for document in documents if document.reading.storage.exists(document.reading.name)}
    return {code:by_id[pk] for code,pk in selected.items() if pk in by_id}
