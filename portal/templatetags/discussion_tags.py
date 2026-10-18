from django import template
register = template.Library()

@register.inclusion_tag('portal/discussion.html', takes_context=True)
def event_discussion(context, key):
    return {'group': context['discussions'][key], 'request': context['request'],
            'identity_verified': context['identity_verified']}

@register.inclusion_tag('portal/public_responses.html', takes_context=True)
def event_responses(context, key):
    return {'responses': context['discussions'][key]['responses']}
