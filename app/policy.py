import re
COUNTRIES = {x.lower(): x for x in ('Kenya', 'Uganda', 'Tanzania')}
def country(value):
    return COUNTRIES.get(value.strip().lower()) if value else None
def name_key(value):
    return ' '.join(value.casefold().split())
def tax_key(value):
    return value.strip().upper()
def fields_error(d):
    if not isinstance(d.get('name'), str) or not 2 <= len(d['name'].strip()) <= 120:
        return 'Company name must contain 2–120 characters.'
    if any(ord(c) < 32 for c in d['name']):
        return 'Company name contains invalid characters.'
    if not country(d.get('country')):
        return 'Only Kenya, Uganda and Tanzania are supported.'
    if not isinstance(d.get('tax_id'), str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{2,31}', d['tax_id']):
        return 'Tax ID must contain 3–32 letters, digits or hyphens.'
    return None
