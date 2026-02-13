"""Profile management package.

Facade: re-exports ProfileBusiness for full backward compatibility.
All existing imports like `from .profile import ProfileBusiness` continue to work.

Internal structure:
- extraction.py  — UI data extraction via ADB (get_complete_profile_info, counts, about account)
- persistence.py — Database save operations (save_profile_to_database)

Analysis/filtering methods (is_profile_suitable_for_interaction, extract_profile_metrics)
have been moved to filtering.py where they belong (single source of truth for all filtering).
"""

from .extraction import ProfileExtraction as ProfileBusiness

__all__ = ['ProfileBusiness']
