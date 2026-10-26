"""Local WCVP checklist: download, verify, and index the Kew data release; no network at match time."""
from contextlib import closing
from datetime import datetime, timezone
import csv
import hashlib
import io
import sqlite3
import urllib.request
import zipfile
from pathlib import Path

from .normalize import epithet_key, genus_key, rank_key

WCVP_URL = 'https://sftp.kew.org/pub/data-repositories/WCVP/wcvp.zip'
CITATION = ('Govaerts R (ed.). WCVP: World Checklist of Vascular Plants. Facilitated by the Royal Botanic '
            'Gardens, Kew. https://doi.org/10.34885/egs6-cp24. Licensed under CC BY 3.0.')
INDEX_SCHEMA = '1'
_NAME_COLUMNS = ('plant_name_id', 'ipni_id', 'powo_id', 'taxon_rank', 'taxon_status', 'family', 'genus', 'species',
                 'species_hybrid', 'infraspecific_rank', 'infraspecies', 'taxon_name', 'taxon_authors',
                 'accepted_plant_name_id', 'homotypic_synonym', 'place_of_publication', 'volume_and_page',
                 'first_published', 'nomenclatural_remarks')


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def download(target, *, url=WCVP_URL):
    """Download a WCVP release to target (never overwritten) and return its SHA-256."""
    target = Path(target)
    if target.exists():
        raise FileExistsError(f'{target} already exists; choose another name to keep releases distinct.')
    partial = target.with_name(target.name + '.partial')
    digest = hashlib.sha256()
    with urllib.request.urlopen(url, timeout=120) as response, open(partial, 'wb') as stream:
        for block in iter(lambda: response.read(1 << 20), b''):
            digest.update(block)
            stream.write(block)
    with zipfile.ZipFile(partial) as archive:
        if {'wcvp_names.csv', 'wcvp_distribution.csv'} - set(archive.namelist()):
            raise ValueError('The download is not a WCVP release (names/distribution files missing).')
    partial.replace(target)
    return digest.hexdigest()


def _rows(archive, member):
    with archive.open(member) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding='utf-8'), delimiter='|', quoting=csv.QUOTE_NONE)
        header = next(reader)
        for row in reader:
            yield dict(zip(header, row))


def build_index(source, target, *, version=None):
    """Index a WCVP zip into a new SQLite file; the release date of the names file is the default version."""
    source, target = Path(source), Path(target)
    if target.exists():
        raise FileExistsError(f'{target} already exists; remove it or choose another index file.')
    csv.field_size_limit(1 << 30)
    partial = target.with_name(target.name + '.partial')
    partial.unlink(missing_ok=True)
    with zipfile.ZipFile(source) as archive, closing(sqlite3.connect(partial)) as db:
        names_date = datetime(*archive.getinfo('wcvp_names.csv').date_time[:3]).date().isoformat()
        db.executescript(f"""
            CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE names({', '.join(c + ' TEXT' for c in _NAME_COLUMNS)},
                               genus_key TEXT, species_key TEXT, rank_key TEXT, infra_key TEXT);
            CREATE TABLE distribution(plant_name_id TEXT, area TEXT, introduced TEXT, extinct TEXT, location_doubtful TEXT);
        """)
        db.executemany(f'INSERT INTO names VALUES ({", ".join("?" * (len(_NAME_COLUMNS) + 4))})', (
            [row.get(c, '') for c in _NAME_COLUMNS] + [genus_key(row['genus']), epithet_key(row['species']),
             rank_key(row['infraspecific_rank']) if row['infraspecies'] else '', epithet_key(row['infraspecies'])]
            for row in _rows(archive, 'wcvp_names.csv')))
        db.executemany('INSERT INTO distribution VALUES (?, ?, ?, ?, ?)', (
            (row['plant_name_id'], row['area'], row['introduced'], row['extinct'], row['location_doubtful'])
            for row in _rows(archive, 'wcvp_distribution.csv')))
        db.executescript("""
            CREATE UNIQUE INDEX names_id ON names(plant_name_id);
            CREATE INDEX names_name ON names(genus_key, species_key, infra_key);
            CREATE INDEX names_accepted ON names(accepted_plant_name_id);
            CREATE INDEX distribution_id ON distribution(plant_name_id);
        """)
        db.executemany('INSERT INTO meta VALUES (?, ?)', [
            ('schema', INDEX_SCHEMA), ('wcvp_version', version or f'WCVP {names_date}'),
            ('source_sha256', sha256_file(source)), ('source_name', source.name),
            ('built_at', datetime.now(timezone.utc).isoformat(timespec='seconds')), ('citation', CITATION)])
        db.commit()
    partial.replace(target)
    return target


class Checklist:
    """Read-only access to an index built by build_index."""

    def __init__(self, path):
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(f'Index not found: {path}. Build it with: powo-nomenclature index WCVP_ZIP INDEX')
        # as_uri() escapes spaces and drive letters (file:///C:/...), so the read-only URI works on every OS.
        self.db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
        self.db.row_factory = sqlite3.Row
        self.meta = dict(self.db.execute('SELECT key, value FROM meta'))
        if self.meta.get('schema') != INDEX_SCHEMA:
            raise ValueError('Index schema differs from this version; rebuild the index.')
        self._genera = None
        self._species = {}

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def find(self, genus, species, infra='', rank=None):
        """Names with these normalized parts; infra='' returns species-level names only."""
        sql = 'SELECT * FROM names WHERE genus_key = ? AND species_key = ? AND infra_key = ?'
        params = [genus, species, infra]
        if rank:
            sql += ' AND rank_key = ?'
            params.append(rank)
        return [dict(row) for row in self.db.execute(sql, params)]

    def get(self, plant_name_id):
        row = self.db.execute('SELECT * FROM names WHERE plant_name_id = ?', (plant_name_id,)).fetchone()
        return dict(row) if row else None

    def synonyms(self, accepted_id):
        return [dict(row) for row in self.db.execute(
            'SELECT * FROM names WHERE accepted_plant_name_id = ? AND plant_name_id != ? AND taxon_status = ?',
            (accepted_id, accepted_id, 'Synonym'))]

    def native_areas(self, plant_name_id):
        return sorted({row[0] for row in self.db.execute(
            "SELECT area FROM distribution WHERE plant_name_id = ? AND introduced = '0'", (plant_name_id,))})

    def introduced_areas(self, plant_name_id):
        return sorted({row[0] for row in self.db.execute(
            "SELECT area FROM distribution WHERE plant_name_id = ? AND introduced = '1'", (plant_name_id,))})

    def genera(self):
        if self._genera is None:
            self._genera = [row[0] for row in self.db.execute('SELECT DISTINCT genus_key FROM names WHERE genus_key != ""')]
        return self._genera

    def species_keys(self, genus):
        if genus not in self._species:
            self._species[genus] = [row[0] for row in self.db.execute(
                'SELECT DISTINCT species_key FROM names WHERE genus_key = ? AND species_key != ""', (genus,))]
        return self._species[genus]
