# Changelog

## 0.1.0a1 — unreleased

- Local WCVP index (`download`, `index`) with the release label, source SHA-256 and citation recorded in every run.
- Matching cascade for historical names: exact name, species when the infraspecific name is absent, spelling rules
  (ligatures æ/œ, glued hybrid signs, Latin endings), closest spelling in the genus, closest genus; homonyms decided by
  author or reported. Historical ranks (proles, lusus), invalid/unplaced names and every non-exact result need review.
- POWO-style fields: link, status and check date describe the name as written; family, name parts, authors, native
  areas and synonyms describe the accepted name.
- Excel workflow with a review workbook (results, differences, source) and a fill-only-empty import file for
  TSennen/Taxa exports; English and Portuguese labels.
