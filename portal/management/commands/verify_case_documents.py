"""Check approved public copies and all protected timeline citation targets."""
import json,re,shutil,subprocess
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from portal.public_case_documents import APPROVED,catalog,page_targets

class Command(BaseCommand):
    help='Verify 28 redacted files, page counts, citations, and optionally write a citation report.'
    def add_arguments(self,parser):
        parser.add_argument('--report',type=Path)
    def handle(self,*args,**options):
        documents,errors=catalog()
        if shutil.which('pdfinfo'):
            for code,row in documents.items():
                if code=='C02':continue
                result=subprocess.run(['pdfinfo',str(Path(settings.BASE_DIR)/row['file'])],capture_output=True,text=True)
                pages=re.search(r'^Pages:\s+(\d+)',result.stdout,re.M)
                if result.returncode or not pages or int(pages[1])!=row['pages']:errors.append(code+': PDF page count mismatch')
        elif any(code!='C02' for code in documents):errors.append('pdfinfo unavailable: actual PDF page counts not verified')
        if 'C02' in documents:
            if shutil.which('identify'):
                result=subprocess.run(['identify','-format','%m %n',str(Path(settings.BASE_DIR)/documents['C02']['file'])],capture_output=True,text=True)
                if result.returncode or result.stdout.strip()!='JPEG 1':errors.append('C02: JPEG decode/image count mismatch')
            else:errors.append('identify unavailable: actual JPEG image not verified')
        from portal.reading_registry import reading_entries
        report=[]
        for entry in reading_entries():
            key=entry['key']
            for reference in entry.get('source_references',[]):
                code,locator=reference['code'],reference['locator']
                state='not included' if code=='S01' else 'missing file'
                if code in documents:
                    try:
                        targets=page_targets(locator,documents[code]['pages']) if code!='C02' else []
                        state='valid'
                    except ValueError:errors.append(code+': invalid citation pages');targets=[];state='invalid pages'
                else:targets=[]
                if code not in APPROVED and code!='S01':errors.append('unknown citation code')
                report.append({'key':key,'code':code,'locator':locator,'file':APPROVED.get(code),'page_targets':targets,'status':state})
        if len({row['key'] for row in report})!=72:errors.append('timeline: expected citations for 72 stable keys')
        if options['report']:
            options['report'].write_text(json.dumps({'files_present':len(documents),'citations':report,'errors':errors},ensure_ascii=False,indent=2))
            options['report'].chmod(0o600)
        for error in errors:self.stderr.write(error)
        if errors:raise CommandError(f'Validation failed: {len(documents)}/28 approved copies present; {len(errors)} errors')
        self.stdout.write(self.style.SUCCESS(f'Validated 28 redacted copies: PDF 27 / 489 pages, JPG 1 / 1 image; {len(report)} citations.'))
