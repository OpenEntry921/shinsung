from django import template
register=template.Library()

@register.inclusion_tag('portal/timeline_document.html',takes_context=True)
def timeline_document(context,code):
    return {'document':context.get('document_links',{}).get(code)}

@register.inclusion_tag('portal/timeline_responses.html',takes_context=True)
def timeline_responses(context,key):
    return {'responses':context['discussions'][key]['responses']}
