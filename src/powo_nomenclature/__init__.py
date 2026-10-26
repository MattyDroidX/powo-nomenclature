"""Match historical plant names to the World Checklist of Vascular Plants and fill POWO-style fields."""
__version__ = '0.1.0a1'

from .match import Match, NameQuery, match_name
from .resolve import FIELDS, Resolution, resolve
from .wcvp import Checklist, build_index, download

__all__ = ['Checklist', 'FIELDS', 'Match', 'NameQuery', 'Resolution', 'build_index', 'download',
           'match_name', 'resolve', '__version__']
