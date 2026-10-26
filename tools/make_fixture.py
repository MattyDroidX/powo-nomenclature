"""Extract the small WCVP sample used by the tests from a full WCVP release (CC BY 3.0, see NOTICE.md).

python tools/make_fixture.py wcvp.zip tests/fixtures/wcvp-mini.zip
"""
import csv
import io
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from powo_nomenclature.normalize import epithet_key, genus_key  # noqa: E402

# Species whose every name (all ranks and authors) is kept, plus genera kept whole for spelling searches.
SPECIES = {('micromeria', 'filiformis'), ('veronica', 'micrantha'), ('xanthium', 'sallentii'), ('xanthium', 'vayredae'),
           ('crataegus', 'brevispina'), ('crataegus', 'monogyna'), ('salvia', 'officinalis'), ('erigeron', 'barcinonensis'),
           ('fumaria', 'queri'), ('mentha', 'rotundifolia'), ('stellaria', 'media'), ('chaerophyllum', 'aureum')}
GENERA = {'calamintha'}
PREFIXES = {('viola', 'ro')}


def read(archive, member):
    with archive.open(member) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding='utf-8'), delimiter='|', quoting=csv.QUOTE_NONE)
        header = next(reader)
        return header, [dict(zip(header, row)) for row in reader]


def wanted(row):
    g, s = genus_key(row['genus']), epithet_key(row['species'])
    return (g, s) in SPECIES or g in GENERA or any(g == pg and s.startswith(p) for pg, p in PREFIXES)


def main(source, target):
    csv.field_size_limit(1 << 30)
    with zipfile.ZipFile(source) as archive:
        names_header, names = read(archive, 'wcvp_names.csv')
        keep = {r['plant_name_id'] for r in names if wanted(r)}
        accepted = {r['accepted_plant_name_id'] for r in names if r['plant_name_id'] in keep and r['accepted_plant_name_id']}
        keep |= accepted | {r['plant_name_id'] for r in names if r['accepted_plant_name_id'] in accepted}
        dist_header, distribution = read(archive, 'wcvp_distribution.csv')
        info = archive.getinfo('wcvp_names.csv')
    with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as out:
        for member, header, rows in (('wcvp_names.csv', names_header, [r for r in names if r['plant_name_id'] in keep]),
                                     ('wcvp_distribution.csv', dist_header, [r for r in distribution if r['plant_name_id'] in keep])):
            text = '\n'.join('|'.join(r[c] for c in header) for r in [dict(zip(header, header)), *rows]) + '\n'
            out.writestr(zipfile.ZipInfo(member, date_time=info.date_time), text)
    print(f'{target}: {len(keep)} names')


if __name__ == '__main__':
    main(*sys.argv[1:3])
