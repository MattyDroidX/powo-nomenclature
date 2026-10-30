"""POWO-style fields: status, link and check date describe the name as written; the rest the accepted name."""
from dataclasses import dataclass, field
from datetime import date

FIELDS = ('powo_family', 'powo_genus', 'powo_specific_epithet', 'powo_author', 'powo_infra_rank',
          'powo_infra_epithet', 'powo_infra_author', 'powo_native', 'powo_synonyms', 'powo_url',
          'powo_status', 'powo_checked_at')
ACCEPTED_FIELDS = FIELDS[:9]
ORIGINAL_FIELDS = FIELDS[9:]
POWO_TAXON_URL = 'https://powo.science.kew.org/taxon/urn:lsid:ipni.org:names:{ipni_id}'
# Excel cells hold at most 32 767 characters; POWO itself collapses long lists the same way.
MAX_SYNONYM_CHARS = 30000
TEXTS = {
    'accepted': 'This {rank} is accepted',
    'synonym': 'This name is a synonym of {accepted}',
    'unplaced': 'This name is unplaced',
    'status': 'This name is {status}',
    'homotypic': 'Homotypic Synonyms',
    'heterotypic': 'Heterotypic Synonyms',
    'many_synonyms': 'Has {count} Synonyms',
}
_RANK_WORDS = {'Species': 'species', 'Subspecies': 'subspecies', 'Variety': 'variety', 'Form': 'form'}


@dataclass
class Resolution:
    values: dict
    original_name: str = ''
    accepted_name: str = ''
    notes: list[str] = field(default_factory=list)
    review: bool = False


def synonym_line(row):
    """«Name Authors in Publication volume: page (year), remarks», with WCVP spacing normalized."""
    parts = [row['taxon_name'], row['taxon_authors']]
    if row['place_of_publication'].strip():
        parts += ['in', row['place_of_publication'], row['volume_and_page']]
    parts.append(row['first_published'])
    line = ' '.join(' '.join(str(p).split()) for p in parts if str(p or '').strip())
    return line + ' '.join(str(row['nomenclatural_remarks'] or '').split())


def synonyms_text(rows, texts=TEXTS):
    groups = [(texts['homotypic'], sorted((r for r in rows if r['homotypic_synonym'] == 'T'), key=lambda r: r['taxon_name'])),
              (texts['heterotypic'], sorted((r for r in rows if r['homotypic_synonym'] != 'T'), key=lambda r: r['taxon_name']))]
    lines = [line for title, members in groups if members for line in [title, *map(synonym_line, members)]]
    text = '\n'.join(lines)
    return texts['many_synonyms'].format(count=len(rows)) if len(text) > MAX_SYNONYM_CHARS else text


def _page(checklist, original, notes):
    """POWO page id of the name as written (POWO also publishes names that have no IPNI record)."""
    if original['powo_id'] or original['ipni_id']:
        return original['powo_id'] or original['ipni_id']
    if original['infraspecies']:
        species = [r for r in checklist.find(original['genus_key'], original['species_key']) if r['ipni_id']]
        if species:
            notes.append(f"«{original['taxon_name']}» has no POWO page; species page linked")
            return species[0]['ipni_id']
    notes.append(f"«{original['taxon_name']}» has no IPNI identifier; link left empty")
    return ''


def _species_author(checklist, accepted):
    rows = [r for r in checklist.find(accepted['genus_key'], accepted['species_key']) if r['taxon_status'] == 'Accepted']
    return rows[0]['taxon_authors'] if rows else ''


def resolve(checklist, match, *, checked_at=None, texts=TEXTS, species_author_for_infraspecific=False):
    """Fill the twelve POWO fields for a Match; nothing is returned for a name not found.

    For an accepted infraspecific name, powo_author is left empty (the infraspecific author goes to
    powo_infra_author) unless species_author_for_infraspecific asks for the species author.
    """
    notes, original = [], match.original
    if original is None:
        return Resolution({}, notes=['no WCVP name'], review=True)
    accepted_id = original['accepted_plant_name_id'] or (original['plant_name_id'] if original['taxon_status'] == 'Accepted' else '')
    accepted = checklist.get(accepted_id) if accepted_id else None
    status = original['taxon_status']
    if status == 'Accepted':
        status_text = texts['accepted'].format(rank=_RANK_WORDS.get(original['taxon_rank'], 'name'))
    elif accepted is not None:
        status_text = texts['synonym'].format(accepted=accepted['taxon_name'])
        if status != 'Synonym':
            notes.append(f'WCVP status of the name as written: {status}')
    elif status == 'Unplaced':
        status_text = texts['unplaced']
    else:
        status_text = texts['status'].format(status=status.lower())
    ipni = _page(checklist, original, notes)
    values = {'powo_url': POWO_TAXON_URL.format(ipni_id=ipni) if ipni else '', 'powo_status': status_text,
              'powo_checked_at': (checked_at or date.today()).strftime('%d/%m/%Y')}
    review = not ipni
    if accepted is None:
        notes.append('no accepted name in WCVP; accepted-name fields left empty')
        return Resolution(values, original['taxon_name'], '', notes, True)
    infraspecific = bool(accepted['infraspecies'])
    native = checklist.native_areas(accepted['plant_name_id'])
    if not native:
        introduced = checklist.introduced_areas(accepted['plant_name_id'])
        notes.append('WCVP lists no native area' + (f"; introduced into: {', '.join(introduced)}" if introduced else ''))
    values.update({
        'powo_family': accepted['family'], 'powo_genus': accepted['genus'], 'powo_specific_epithet': accepted['species'],
        'powo_author': (_species_author(checklist, accepted) if species_author_for_infraspecific else '') if infraspecific else accepted['taxon_authors'],
        'powo_infra_rank': accepted['infraspecific_rank'] if infraspecific else '',
        'powo_infra_epithet': accepted['infraspecies'] if infraspecific else '',
        'powo_infra_author': accepted['taxon_authors'] if infraspecific else '',
        'powo_native': ', '.join(native),
        'powo_synonyms': synonyms_text(checklist.synonyms(accepted['plant_name_id']), texts),
    })
    return Resolution(values, original['taxon_name'], accepted['taxon_name'], notes, review)
