"""Single publication switch for the voluntary fund; no personal deposit records."""

# Enter only information approved for public display. Switch status to 'published'
# after account_number AND account_holder are confirmed. Blank optional fields
# are omitted. Preparing/incomplete accounts never reach public HTML.
FUNDRAISING = {
    'status': 'preparing',
    'bank_name': '카카오뱅크',
    'account_number': '',
    'account_holder': '',
    'manager': '',
    'contact': '',
}


def fundraising_context():
    data = {key: value.strip() for key, value in FUNDRAISING.items()}
    ready = data['status'] == 'published' and bool(data['account_number'] and data['account_holder'])
    public = {'bank_name': data['bank_name'], 'account_ready': ready}
    if ready:
        public.update({key: data[key] for key in ('account_number', 'account_holder', 'manager', 'contact')})
    return public
