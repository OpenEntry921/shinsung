from django import template
register=template.Library()

@register.inclusion_tag('portal/timeline_document.html',takes_context=True)
def timeline_document(context,code,locator=""):
    from portal.public_case_documents import public_links
    if not locator:
        entry=context.get('entry',{})
        references=[ref for ref in entry.get('source_references',[]) if ref['code']==code]
        positions=context.render_context.setdefault('timeline_source_positions',{})
        key=(entry.get('key'),code);position=positions.get(key,0)
        positions[key]=position+1
        locator=references[position]['locator'] if position<len(references) else ''
    public=public_links(code,locator)
    document=context.get('document_links',{}).get(code)
    if public.get('public_links'):return public
    if document:return {'document':document}
    return public or {'document':None}

@register.inclusion_tag('portal/timeline_responses.html',takes_context=True)
def timeline_responses(context,key):
    return {'responses':context['discussions'][key]['responses']}
