"""Match historical plant names to the World Checklist of Vascular Plants and fill POWO-style fields."""
__version__ = '0.1.0a2'

from .match import Match, NameQuery, match_name
from .resolve import FIELDS, Resolution, resolve
from .verify import Issue, verify
from .wcvp import Checklist, build_index, download

__all__ = ['Checklist', 'FIELDS', 'Issue', 'Match', 'NameQuery', 'Resolution', 'build_index', 'download',
           'match_name', 'resolve', 'verify', '__version__']
