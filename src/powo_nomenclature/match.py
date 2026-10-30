"""Cascade from the most to the least certain way of finding a historical name in WCVP."""
from dataclasses import dataclass, field
from difflib import SequenceMatcher, get_close_matches

from .normalize import HISTORICAL_RANKS, author_similarity, clean_infra, epithet_key, epithet_variants, genus_key

_STATUS_ORDER = {'Accepted': 0, 'Synonym': 1}


@dataclass(frozen=True)
class NameQuery:
    genus: str
    species: str
    author: str = ''
    infra_rank: str = ''
    infra_epithet: str = ''
    infra_author: str = ''

    def text(self):
        return ' '.join(str(p).strip() for p in (self.genus, self.species, self.infra_rank, self.infra_epithet) if str(p or '').strip())


@dataclass
class Match:
    """original is the WCVP row of the name as written (None when nothing was found).

    method: exact, infra-rank-variant, infra-fuzzy, species-fallback, historical-rank, orthographic, fuzzy,\n    fuzzy-genus or none.
    review: True whenever a person should confirm the choice before it is used.
    """
    query: NameQuery
    original: dict | None
    method: str
    score: float = 1.0
    review: bool = False
    notes: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)


def _choose(rows, author, notes):
    """Pick among homonyms by author; ambiguity is reported, never resolved silently."""
    if len(rows) <= 1:
        return (rows[0] if rows else None), False
    ranked = sorted(rows, key=lambda r: (-author_similarity(author, r['taxon_authors']),
                                         _STATUS_ORDER.get(r['taxon_status'], 2), not r['ipni_id']))
    best, second = ranked[0], ranked[1]
    if author_similarity(author, best['taxon_authors']) > author_similarity(author, second['taxon_authors']):
        notes.append(f'{len(rows)} WCVP names with this spelling; author «{author}» chose «{best["taxon_authors"]}»')
        return best, False
    if len({r['accepted_plant_name_id'] or r['plant_name_id'] for r in rows}) == 1:
        return best, False  # Same taxon either way.
    notes.append(f'{len(rows)} WCVP names with this spelling and no decisive author: '
                 + '; '.join(f'{r["taxon_name"]} {r["taxon_authors"]} ({r["taxon_status"]})' for r in ranked[:4]))
    return best, True


def _species_level(checklist, genus, species, author, notes, *, fuzzy_cutoff):
    """(rows, method, score) for a species name using exact, spelling-variant and fuzzy lookups."""
    rows = checklist.find(genus, species)
    if rows:
        return rows, 'exact', 1.0
    for variant in epithet_variants(species):
        rows = checklist.find(genus, variant)
        if rows:
            notes.append(f'spelling variant: «{species}» → «{variant}»')
            return rows, 'orthographic', SequenceMatcher(None, species, variant).ratio()
    close = get_close_matches(species, checklist.species_keys(genus), n=3, cutoff=fuzzy_cutoff)
    if close:
        notes.append(f'closest spelling in the genus: «{species}» → «{close[0]}»'
                     + (f' (also: {", ".join(close[1:])})' if close[1:] else ''))
        return checklist.find(genus, close[0]), 'fuzzy', SequenceMatcher(None, species, close[0]).ratio()
    return [], 'none', 0.0


def _hints(checklist, genus, species, cutoff=0.6):
    """Nearest WCVP spellings shown to the reviewer; none is chosen."""
    if genus in set(checklist.genera()):
        close = get_close_matches(species, checklist.species_keys(genus), n=3, cutoff=cutoff)
        names = [f'{genus.capitalize()} {epithet}' for epithet in close]
    else:
        names = [g.capitalize() for g in get_close_matches(genus, checklist.genera(), n=3, cutoff=cutoff)]
    return [f'closest WCVP names, not chosen: {", ".join(names)}'] if names else []


def match_name(checklist, query, *, fuzzy_cutoff=0.85, review_species_fallback=False):
    """Find the WCVP row for a name as written. Only exact and documented species-level results skip review."""
    notes = []
    genus, species = genus_key(query.genus), epithet_key(query.species)
    if not genus or not species:
        return Match(query, None, 'none', 0.0, True, ['genus or specific epithet missing'])
    rank, infra, infra_notes = clean_infra(query.infra_rank, query.infra_epithet)
    notes += infra_notes
    review = bool(infra_notes)
    author = query.infra_author if infra else query.author

    historical = rank in HISTORICAL_RANKS
    if historical:
        notes.append(f'historical rank «{query.infra_rank}»: confirm how the name is cited today')
        review = True
    if infra:
        # Exact name first: WCVP also lists names at historical ranks («Stellaria media proles catalaunica»).
        rows, method, score = checklist.find(genus, species, infra, rank or None), 'exact', 1.0
        if not rows:
            rows = checklist.find(genus, species, infra)
            if rows:
                method = 'infra-rank-variant'
                notes.append(f'rank differs: written «{query.infra_rank}», WCVP «{rows[0]["infraspecific_rank"]}»')
        if not rows:
            close = get_close_matches(infra, checklist.infra_keys(genus, species), n=3, cutoff=fuzzy_cutoff)
            if close:
                rows, method = checklist.find(genus, species, close[0]), 'infra-fuzzy'
                score = SequenceMatcher(None, infra, close[0]).ratio()
                notes.append(f'closest infraspecific spelling in the species: «{infra}» → «{close[0]}»')
        if rows:
            original, ambiguous = _choose(rows, author, notes)
            if original['taxon_status'] not in ('Accepted', 'Synonym'):
                notes.append(f"WCVP status «{original['taxon_status']}»: confirm which name to cite")
                ambiguous = True
            return Match(query, original, method, round(score, 3), review or ambiguous or method != 'exact', notes, rows)
        if historical:
            # «Salvia officinalis proles S. iberica»: the epithet may stand for a species of its own.
            rows = checklist.find(genus, infra)
            if rows:
                notes.append(f'«{infra}» checked as a species')
                original, _ = _choose(rows, query.infra_author, notes)
                return Match(query, original, 'historical-rank', 1.0, True, notes, rows)
            notes.append(f'«{infra}» is not in WCVP as a species either; species name used')
            method_prefix = 'historical-rank'
        else:
            notes.append(f'«{query.text()}» not in WCVP; species name used')
            method_prefix, review = 'species-fallback', review or review_species_fallback
    else:
        method_prefix = ''

    current_genus = genus
    rows, method, score = _species_level(checklist, genus, species, query.author, notes, fuzzy_cutoff=fuzzy_cutoff)
    if not rows and genus not in set(checklist.genera()):
        close = get_close_matches(genus, checklist.genera(), n=1, cutoff=fuzzy_cutoff)
        if close:
            current_genus = close[0]
            notes.append(f'genus not in WCVP: «{genus}» → «{current_genus}»')
            rows, method, score = _species_level(checklist, current_genus, species, query.author, notes,
                                                 fuzzy_cutoff=fuzzy_cutoff)
            method = 'fuzzy-genus' if rows else 'none'
            score *= SequenceMatcher(None, genus, current_genus).ratio()
    if not rows:
        notes.append('no WCVP name found; check the spelling or the protologue')
        notes += _hints(checklist, current_genus, species)
        return Match(query, None, 'none', 0.0, True, notes)
    original, ambiguous = _choose(rows, query.author, notes)
    if method_prefix and method == 'exact':
        method = method_prefix
    review = review or ambiguous or method not in ('exact', 'species-fallback')
    if original is not None and original['taxon_status'] not in ('Accepted', 'Synonym'):
        notes.append(f"WCVP status «{original['taxon_status']}»: confirm which name to cite")
        review = True
    return Match(query, original, method, round(score, 3), review, notes, rows)
