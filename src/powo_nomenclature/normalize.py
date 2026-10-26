"""Comparison keys for historical botanical names; source spellings are never rewritten."""
import re
import unicodedata

_LIGATURES = str.maketrans({'æ': 'ae', 'Æ': 'Ae', 'œ': 'oe', 'Œ': 'Oe', 'ß': 'ss'})
_RANKS = {'f': 'f.', 'fa': 'f.', 'fo': 'f.', 'form': 'f.', 'forma': 'f.', 'var': 'var.', 'v': 'var.', 'varietas': 'var.',
          'subsp': 'subsp.', 'ssp': 'subsp.', 'subspecies': 'subsp.', 'subvar': 'subvar.', 'subf': 'subf.',
          'proles': 'proles', 'prol': 'proles', 'race': 'proles', 'lusus': 'lusus'}
# Rank words whose names cannot be looked up as such today; they always need a person's decision.
HISTORICAL_RANKS = {'proles', 'lusus'}
# Latin endings that historical and current spellings often swap (gender agreement and genitives).
_ENDINGS = (('ensis', 'ense'), ('ense', 'ensis'), ('us', 'a'), ('us', 'um'), ('a', 'us'), ('a', 'um'), ('um', 'us'),
            ('um', 'a'), ('ii', 'i'), ('i', 'ii'), ('is', 'e'), ('e', 'is'), ('iae', 'ia'), ('ae', 'a'))


def fold(value):
    """Lowercase ASCII with ligatures expanded and the hybrid sign removed."""
    value = str(value or '').translate(_LIGATURES).replace('×', ' ')
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9.\- ]+', ' ', value)).strip()


def genus_key(value):
    words = fold(value).replace('.', ' ').split()
    if words and words[0] == 'x' and len(words) > 1:
        words = words[1:]
    return words[0] if words else ''


def epithet_key(value):
    words = [w for w in fold(value).replace('.', ' ').split() if w != 'x']
    return words[0] if words else ''


def rank_key(value):
    word = fold(value).strip('. ')
    return _RANKS.get(word, (word + '.') if word else '')


def clean_infra(rank, epithet):
    """(rank key, epithet key, notes) from free-text infraspecific columns."""
    notes = []
    raw = str(epithet or '').strip()
    words = [w for w in fold(epithet).replace('.', ' ').split() if w != 'x']
    while words and len(words[0]) < 3 and len(words) > 1:
        words = words[1:]  # abbreviated genus before the epithet: «S. iberica»
    first = words[0] if words else ''
    # «'= F. major x capreolata»: an annotated synonymy or comment, not an epithet.
    note = raw.lstrip("'\" ").startswith('=') or (not str(rank or '').strip() and len(words) > 1)
    if note or not re.fullmatch(r'[a-z][a-z-]{2,}', first or '-'):
        if str(epithet or '').strip():
            notes.append(f'infraspecific text ignored: «{str(epithet).strip()}»')
        return '', '', notes
    if len(words) > 1:
        notes.append(f'extra infraspecific text ignored: «{str(epithet).strip()}»')
    key = rank_key(rank)
    if not key and str(rank or '').strip() == '':
        notes.append('infraspecific epithet without rank')
    return key, first, notes


def epithet_variants(key):
    """Spelling variants to try when the exact epithet is absent, nearest first."""
    variants = []
    if key.startswith('x') and len(key) > 4 and key[1] not in 'aeiouy':
        variants.append(key[1:])  # hybrid sign glued to the epithet: «xqueri»
    for old, new in _ENDINGS:
        if key.endswith(old) and len(key) - len(old) >= 3:
            variants.append(key[:-len(old)] + new)
    return list(dict.fromkeys(v for v in variants if v != key))


def author_tokens(value):
    # «Cav. non L.»: what follows non/nec names the author excluded, not the author of this name.
    value = re.split(r'\b(?:non|nec)\b', fold(value))[0]
    return [w for w in re.split(r'[^a-z]+', value) if w and w not in {'et', 'ex', 'in', 'and', 'apud'}]


def _same_author(wanted, available):
    if len(wanted) == 1 or len(available) == 1:
        return wanted == available  # «L.» is Linnaeus, not any author starting with L.
    return available.startswith(wanted) or wanted.startswith(available)


def author_similarity(query, candidate):
    """Share of the query's author words that abbreviate (or are abbreviated by) a candidate author word."""
    wanted, available = author_tokens(query), author_tokens(candidate)
    if not wanted or not available:
        return 0.0
    return sum(1 for w in wanted if any(_same_author(w, a) for a in available)) / len(wanted)
