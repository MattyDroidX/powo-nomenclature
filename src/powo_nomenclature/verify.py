"""Audit POWO fields already filled (by hand, by another tool or by an AI) against WCVP."""
from dataclasses import dataclass
import re

from .match import match_name
from .normalize import clean_infra, epithet_key, genus_key

MESSAGES = {
    'en': {
        'unknown_page': 'The link points to {page}, which is not in WCVP',
        'link_not_name_as_written': 'The link is the page of {linked}, not of the name as written',
        'unplaced_has_accepted': '{linked} is unplaced in WCVP: there is no accepted name, so the accepted-name fields should be empty',
        'accepted_not_accepted': '{given} is not an accepted name in WCVP',
        'link_accepted_mismatch': 'The link leads to the accepted name {expected}, not to {given}',
        'family_differs': 'Family {given}; WCVP gives {expected}',
        'native_differs': 'Native areas differ from WCVP: missing {missing}; not native {extra}',
    },
    'pt': {
        'unknown_page': 'O link aponta para {page}, que não existe no WCVP',
        'link_not_name_as_written': 'O link é a página de {linked}, não do nome como escrito',
        'unplaced_has_accepted': '{linked} está «unplaced» no WCVP: não há nome aceite, por isso os campos do nome aceite devem ficar vazios',
        'accepted_not_accepted': '{given} não é um nome aceite no WCVP',
        'link_accepted_mismatch': 'O link leva ao nome aceite {expected}, não a {given}',
        'family_differs': 'Família {given}; o WCVP indica {expected}',
        'native_differs': 'Áreas nativas diferentes do WCVP: faltam {missing}; não nativas {extra}',
    },
}


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


def page_id(url):
    """«…/urn:lsid:ipni.org:names:77283132-1» or «…/taxon/77283132-1?…» → 77283132-1."""
    match = re.search(r'(\d+-\d)(?:\D|$)', str(url or ''))
    return match[1] if match else ''


def _areas(text):
    return {a.strip() for a in str(text or '').split(',') if a.strip()}


def _name(values):
    parts = [values.get(f, '') for f in ('powo_genus', 'powo_specific_epithet', 'powo_infra_rank', 'powo_infra_epithet')]
    return ' '.join(str(p).strip() for p in parts if str(p or '').strip())


def verify(checklist, query, values, *, lang='en'):
    """Issues found in the filled POWO fields of one record; an empty list means they agree with WCVP."""
    text, issues = MESSAGES[lang], []

    def add(code, **context):
        issues.append(Issue(code, text[code].format(**context)))

    values = {k: str(v or '').strip() for k, v in values.items()}
    pid = page_id(values.get('powo_url'))
    page = checklist.by_page(pid) if pid else None
    if pid and page is None:
        add('unknown_page', page=pid)
    given = _name(values)
    _, infra, _ = clean_infra(values.get('powo_infra_rank'), values.get('powo_infra_epithet'))
    accepted = [r for r in checklist.find(genus_key(values.get('powo_genus')), epithet_key(values.get('powo_specific_epithet')), infra)
                if r['taxon_status'] == 'Accepted'] if given else []
    if page is not None:
        written = (genus_key(page['genus']), epithet_key(page['species'])) == (genus_key(query.genus), epithet_key(query.species))
        found = match_name(checklist, query).original
        if not written and not (found and found['plant_name_id'] == page['plant_name_id']):
            add('link_not_name_as_written', linked=page['taxon_name'])
        if page['taxon_status'] == 'Unplaced' and given:
            add('unplaced_has_accepted', linked=page['taxon_name'])
        target = page['accepted_plant_name_id'] or (page['plant_name_id'] if page['taxon_status'] == 'Accepted' else '')
        if given and accepted and target and target not in {r['plant_name_id'] for r in accepted}:
            expected = checklist.get(target)
            add('link_accepted_mismatch', expected=expected['taxon_name'] if expected else target, given=given)
    if given and not accepted and not (page is not None and page['taxon_status'] == 'Unplaced'):
        add('accepted_not_accepted', given=given)
    if accepted:
        row = accepted[0]
        if values.get('powo_family') and values['powo_family'] != row['family']:
            add('family_differs', given=values['powo_family'], expected=row['family'])
        if values.get('powo_native'):
            expected, filled = set(checklist.native_areas(row['plant_name_id'])), _areas(values['powo_native'])
            if expected != filled:
                add('native_differs', missing=', '.join(sorted(expected - filled)) or '—', extra=', '.join(sorted(filled - expected)) or '—')
    return issues
