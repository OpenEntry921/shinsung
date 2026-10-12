from django.db import migrations

def preserve_links(apps,schema_editor):
    Document=apps.get_model('portal','Document')
    Evidence=apps.get_model('portal','CaseEvidence')
    for document in Document.objects.exclude(case_id=None).iterator():
        Evidence.objects.get_or_create(case_id=document.case_id,document_id=document.pk,locator='기존 자료 연결 · 페이지·문단 재확인 필요',defaults={'checked':False})

class Migration(migrations.Migration):
    dependencies=[('portal','0006_article_applicability_reason_and_more')]
    operations=[migrations.RunPython(preserve_links,migrations.RunPython.noop)]
