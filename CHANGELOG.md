# Changelog

## 0.1.0a3 — unreleased

- An index refused for being built by another version is closed before the error, so it can be deleted or replaced
  on Windows. 0.1.0a2 was only published on TestPyPI; 0.1.0a3 carries all of its changes.

## 0.1.0a2 — TestPyPI only

Lessons from comparing the results with a spreadsheet filled with the help of a general-purpose AI:

- Infraspecific names: the exact name is tried first, also at historical ranks that WCVP lists
  (*Stellaria media* proles *catalaunica*); then the same epithet at another rank; then the closest spelling of the
  infraspecific epithet within the species (`infra-fuzzy`, reviewed) before falling back to the species.
- Names with no match list the nearest WCVP spellings in the notes (for example *Pinguicula eliae*), without choosing.
- `verify` command and `verify()` function audit POWO fields already filled by hand or by another tool: unknown page
  identifiers, links that are not the page of the name as written, accepted-name fields on unplaced names, names
  that WCVP does not accept, links leading to another accepted name, family and native areas.
- `--species-author-for-infraspecific`: fill `powo_author` with the species author when the accepted name is
  infraspecific (default unchanged: empty).
- The index now has lookups by POWO/IPNI identifier (schema 2). **Rebuild indexes made with 0.1.0a1** with
  `powo-nomenclature index WCVP_ZIP NEW_INDEX`; old ones are refused with that instruction.

## 0.1.0a1 — unreleased

- Local WCVP index (`download`, `index`) with the release label, source SHA-256 and citation recorded in every run.
- Matching cascade for historical names: exact name, species when the infraspecific name is absent, spelling rules
  (ligatures æ/œ, glued hybrid signs, Latin endings), closest spelling in the genus, closest genus; homonyms decided by
  author or reported. Historical ranks (proles, lusus), invalid/unplaced names and every non-exact result need review.
- POWO-style fields: link, status and check date describe the name as written; family, name parts, authors, native
  areas and synonyms describe the accepted name.
- Excel workflow with a review workbook (results, differences, source) and a fill-only-empty import file for
  TSennen/Taxa exports; English and Portuguese labels.
