"""powo-nomenclature: download/index WCVP once, then match names offline."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .match import NameQuery, match_name
from .resolve import resolve
from .wcvp import Checklist, build_index, download


def parse_name(text):
    """«Genus species [rank epithet]» → NameQuery; authors come from --author/--infra-author."""
    words = text.split()
    if len(words) < 2:
        raise ValueError('Write at least a genus and a specific epithet.')
    if len(words) >= 4:
        return NameQuery(words[0], words[1], infra_rank=words[2], infra_epithet=' '.join(words[3:]))
    return NameQuery(words[0], words[1])


def main(argv=None):
    parser = argparse.ArgumentParser(prog='powo-nomenclature', description=__doc__)
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    commands = parser.add_subparsers(dest='command', required=True)
    get = commands.add_parser('download', help='Download the current WCVP release from Kew.')
    get.add_argument('output', type=Path, help='New file, for example wcvp-2026-06.zip')
    index = commands.add_parser('index', help='Build the local SQLite index from a WCVP zip.')
    index.add_argument('wcvp', type=Path)
    index.add_argument('index', type=Path)
    index.add_argument('--version-label', help='Release label recorded in results (default: WCVP <names file date>).')
    name = commands.add_parser('name', help='Match one name and print the POWO fields as JSON.')
    name.add_argument('name', help='«Genus species» or «Genus species rank epithet»')
    name.add_argument('--index', type=Path, required=True)
    name.add_argument('--author', default='')
    name.add_argument('--infra-author', default='')
    name.add_argument('--species-author-for-infraspecific', action='store_true',
                      help='Fill powo_author with the species author when the accepted name is infraspecific.')
    sheet = commands.add_parser('excel', help='Process a spreadsheet (default columns: Taxa/TSennen export).')
    sheet.add_argument('input', type=Path)
    sheet.add_argument('--index', type=Path, required=True)
    sheet.add_argument('--output-dir', type=Path, required=True)
    sheet.add_argument('--sheet', help='Worksheet name (default: the first).')
    sheet.add_argument('--lang', choices=('en', 'pt'), default='en')
    sheet.add_argument('--include-review', action='store_true', help='Also put rows that need review in the import file.')
    sheet.add_argument('--overwrite', action='store_true', help='Replace values already filled (default: keep them).')
    sheet.add_argument('--species-author-for-infraspecific', action='store_true',
                       help='Fill powo_author with the species author when the accepted name is infraspecific.')
    audit = commands.add_parser('verify', help='Audit POWO fields already filled in a spreadsheet against WCVP.')
    audit.add_argument('input', type=Path)
    audit.add_argument('--index', type=Path, required=True)
    audit.add_argument('--output-dir', type=Path, required=True)
    audit.add_argument('--sheet', help='Worksheet name (default: the first).')
    audit.add_argument('--lang', choices=('en', 'pt'), default='en')
    args = parser.parse_args(argv)

    if args.command == 'download':
        print(f'{args.output}: sha256 {download(args.output)}')
    elif args.command == 'index':
        build_index(args.wcvp, args.index, version=args.version_label)
        print(f'Index ready: {args.index}')
    elif args.command == 'name':
        query = parse_name(args.name)
        query = NameQuery(query.genus, query.species, args.author, query.infra_rank, query.infra_epithet, args.infra_author)
        with Checklist(args.index) as checklist:
            match = match_name(checklist, query)
            result = resolve(checklist, match, species_author_for_infraspecific=args.species_author_for_infraspecific)
            print(json.dumps({'name': query.text(), 'method': match.method, 'score': match.score,
                              'review': match.review or result.review, 'notes': match.notes + result.notes,
                              'wcvp_version': checklist.meta['wcvp_version'], 'fields': result.values},
                             ensure_ascii=False, indent=2))
    elif args.command == 'verify':
        from .excel import verify_workbook
        with Checklist(args.index) as checklist:
            path, codes, checked = verify_workbook(args.input, checklist, args.output_dir, sheet=args.sheet, lang=args.lang)
        print(f'{checked} rows checked · {sum(codes.values())} issues' + (': ' + ', '.join(f'{c}: {n}' for c, n in codes.most_common()) if codes else ''))
        print(f'Report: {path}')
    else:
        from .excel import process_workbook
        with Checklist(args.index) as checklist:
            review, imported, methods = process_workbook(
                args.input, checklist, args.output_dir, sheet=args.sheet, lang=args.lang,
                overwrite=args.overwrite, include_review=args.include_review,
                species_author_for_infraspecific=args.species_author_for_infraspecific)
        print(f'{sum(methods.values())} names · ' + ', '.join(f'{m}: {n}' for m, n in methods.most_common()))
        print(f'Review: {review}' + (f'\nImport: {imported}' if imported else '\nNo import file (no id column or nothing to fill).'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
