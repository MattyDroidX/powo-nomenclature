# powo-nomenclature

Match historical plant names (herbarium labels, old spreadsheets) to the **World Checklist of Vascular Plants (WCVP)**
from the Royal Botanic Gardens, Kew, offline, and fill the fields researchers usually copy by hand from
[Plants of the World Online](https://powo.science.kew.org): accepted family, genus, epithets and authors, native areas,
synonyms, the POWO link and status. Every non-exact decision is flagged for a person to review.

**Português:** liga nomes científicos antigos ao WCVP sem acesso à rede e preenche os campos POWO (nome aceite, autores,
distribuição nativa, sinónimos, link e estado); tudo o que não seja exato fica marcado para revisão. Ver
[Instalar](#install).
**Español:** vincula nombres científicos históricos con el WCVP sin conexión y rellena los campos POWO; todo lo que no
sea exacto queda marcado para revisión. Ver [Instalar](#install).

This project is not affiliated with Kew. Cite WCVP when you publish results (see [NOTICE.md](NOTICE.md)).

## Install

Python 3.11+, no required dependencies; the `excel` extra adds spreadsheet support.

```sh
python -m pip install "powo-nomenclature[excel]"
powo-nomenclature download wcvp-2026-06.zip        # ~85 MB from Kew
powo-nomenclature index wcvp-2026-06.zip wcvp.sqlite  # ~525 MB local index, built once
```

Download a new release when Kew publishes one and build a new index; the release label is recorded in every result.

## Match one name

```sh
powo-nomenclature name "Micromeria filiformis var. glandulosa" --index wcvp.sqlite
```

```python
from powo_nomenclature import Checklist, NameQuery, match_name, resolve

with Checklist("wcvp.sqlite") as checklist:
    match = match_name(checklist, NameQuery("Veronica", "micrantha", author="Hoff. et LK."))
    result = resolve(checklist, match)
print(match.method, match.review, match.notes)
print(result.values["powo_status"], result.values["powo_url"])
```

## Process a spreadsheet

```sh
powo-nomenclature excel export.xlsx --index wcvp.sqlite --output-dir results --lang pt
```

The default columns are those of a TSennen/Taxa complete export (`porto_genus`, `porto_specific_epithet`,
`porto_author`, `porto_infra_rank`, `porto_infra_epithet`, `porto_infra_author`). Two files are written; the input is
never modified:

- `*-powo-review.xlsx`: one row per name with the method, score, review flag and notes; the differences between
  values already filled and the proposal; the WCVP release and citation.
- `*-powo-import.xlsx` (when the input has an `id` column): `id`, `revision` and the twelve POWO fields, only for
  rows that need no review, filling only empty fields. In Taxa, import it with "fill only empty fields".

Use `--include-review` to add the flagged rows, `--overwrite` to replace values already filled and
`--species-author-for-infraspecific` to put the species author in `powo_author` when the accepted name is
infraspecific (by default it stays empty and the author goes to `powo_infra_author`).

## Audit a spreadsheet already filled

```sh
powo-nomenclature verify filled.xlsx --index wcvp.sqlite --output-dir results --lang pt
```

For POWO fields copied by hand or produced by another tool, `*-powo-verify.xlsx` lists, per row: page identifiers
that do not exist, links that are not the page of the name as written, accepted-name fields filled for unplaced names
(which have no accepted name), names WCVP does not accept, links leading to another accepted name, and family or
native areas that differ from WCVP.

## Rules

| Fields | Describe |
| --- | --- |
| `powo_url`, `powo_status`, `powo_checked_at` | the name **as written** (its own POWO page, even when it is a synonym) |
| `powo_family`, `powo_genus`, `powo_specific_epithet`, `powo_author`, `powo_infra_rank`, `powo_infra_epithet`, `powo_infra_author`, `powo_native`, `powo_synonyms` | the **accepted** name |

Matching, from most to least certain: exact name (`exact`, including names WCVP lists at historical ranks); a
different rank with the same epithet (`infra-rank-variant`); the closest infraspecific spelling within the species
(`infra-fuzzy`); the species when the form/variety is not in WCVP (`species-fallback`); spelling rules such as æ/œ,
glued hybrid signs and Latin endings (`orthographic`); the closest epithet in the genus (`fuzzy`); the closest genus
(`fuzzy-genus`). Names with several WCVP homonyms are decided by author or reported; names with no match list the
nearest WCVP spellings in the notes without choosing one. Historical ranks (*proles*,
*lusus*), invalid, illegitimate and unplaced names, and every result other than `exact`/`species-fallback`, are marked
for review. Native areas are WCVP areas where the taxon is not introduced; synonyms are grouped as homotypic and
heterotypic with their place of publication.

The accepted name is Kew's current taxonomic opinion; the scientific decision remains the researcher's.

## Develop

```sh
python -m pip install -e ".[excel]"
python -m unittest discover -s tests -v
python tools/make_fixture.py wcvp.zip tests/fixtures/wcvp-mini.zip   # refresh the test extract
```

The tests run on a small WCVP extract, with reference cases resolved by hand by a researcher on POWO.
