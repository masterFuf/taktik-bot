"""Every version override must land on a field that can actually be written.

The locale refactor turned a number of selector lists into computed properties
(``field = _field_base + L("domain.field")``). A property cannot be assigned, so an override
aimed at one is skipped with a warning: it does not break anything visibly, it simply does
NOTHING. That is how the Instagram comment field stayed unreachable from v417 to v442 while
the correct id sat in the YAML the whole time.

These tests read the shipped override files and fail on a key that would be silently dropped.
"""

from pathlib import Path

import pytest
import yaml

from taktik.core.compat.selectors.setup import (
    INSTAGRAM_SELECTOR_DOMAINS,
    TIKTOK_SELECTOR_DOMAINS,
)

DOMAINS = {"instagram": INSTAGRAM_SELECTOR_DOMAINS, "tiktok": TIKTOK_SELECTOR_DOMAINS}
OVERRIDES_DIR = Path(__file__).resolve().parents[3] / "taktik" / "core" / "compat" / "data" / "overrides"


def _override_keys():
    """(app, version, 'domain.field') for every override shipped, all versions."""
    for app in DOMAINS:
        path = OVERRIDES_DIR / f"{app}.yaml"
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for version, overrides in (data.get("versions") or {}).items():
            for key in overrides or {}:
                yield app, str(version), key


def test_override_files_are_present_and_readable():
    keys = list(_override_keys())
    assert keys, f"no override key found under {OVERRIDES_DIR}"


def _override_entries(app, version, key):
    data = yaml.safe_load((OVERRIDES_DIR / f"{app}.yaml").read_text(encoding="utf-8")) or {}
    return (data.get("versions") or {})[version][key]


@pytest.mark.parametrize("app,version,key", list(_override_keys()))
def test_a_str_target_carries_a_single_entry(app, version, key):
    """A str field takes the first entry only: the others would sit there doing nothing."""
    domain_name, _, field_name = key.partition(".")
    singleton = DOMAINS[app].get(domain_name)
    if singleton is None or not isinstance(getattr(singleton, field_name, None), str):
        return
    entries = _override_entries(app, version, key)
    assert not isinstance(entries, list) or len(entries) == 1, (
        f"{app} v{version}: '{key}' is a str field; {len(entries)} entries, only the first applies")


@pytest.mark.parametrize("app,version,key", list(_override_keys()))
def test_override_targets_a_writable_field(app, version, key):
    domain_name, _, field_name = key.partition(".")
    singleton = DOMAINS[app].get(domain_name)
    assert singleton is not None, f"{app} v{version}: unknown domain '{domain_name}' in '{key}'"
    assert hasattr(singleton, field_name), (
        f"{app} v{version}: '{key}' targets no field on {type(singleton).__name__}"
    )
    assert not isinstance(getattr(type(singleton), field_name, None), property), (
        f"{app} v{version}: '{key}' targets a read-only property on "
        f"{type(singleton).__name__} — the override would be silently skipped. "
        f"Target '_{field_name}_base' instead, carrying the baseline entries along."
    )


# --- what the writable-field test could not see: a target that is not a real object ---

def test_no_domain_points_at_a_facade():
    """A registered domain must be a dataclass INSTANCE, never a `__getattr__` view.

    `hasattr` succeeds through a facade and `dataclasses.fields()` follows its forwarding, so the
    writable-field test above passes on one — while a patch aimed at it is written onto the facade
    as a phantom attribute and production, which imports the objects behind it, sees nothing.
    Measured: patching `VIDEO_SELECTORS` reported "6 selector value(s) patched" and changed zero.
    """
    from dataclasses import is_dataclass

    for platform, domains in DOMAINS.items():
        for name, singleton in domains.items():
            assert is_dataclass(singleton) and not isinstance(singleton, type), (
                f"{platform}.{name} is a {type(singleton).__name__}, not a dataclass instance — "
                "register the catalogues behind it instead"
            )


def _catalogues_defined_under(package):
    """Every selector catalogue the modules of `package` hold, by identity: {id: name}.

    Walked module by module, not read off the barrel's `__all__`: a catalogue the barrel does not
    export is out of the map too, and a guard that reads the barrel cannot see it. The facades are
    not dataclass instances and are left out.
    """
    import importlib
    import pkgutil
    from dataclasses import is_dataclass

    found = {}
    for module_info in pkgutil.walk_packages(package.__path__, package.__name__ + "."):
        module = importlib.import_module(module_info.name)
        for name, obj in vars(module).items():
            if name.endswith("SELECTORS") and is_dataclass(obj) and not isinstance(obj, type):
                found.setdefault(id(obj), name)
    return found


#: TikTok catalogues still out of the map, and why. The list only shrinks: registering one makes the
#: test below red until it leaves the list, and so does a new catalogue left out of the map.
TIKTOK_CATALOGUES_OUT_OF_THE_MAP = {
    "PUBLISH_TEXT_POST_SELECTORS": "exported by flows/, not by the root barrel; registering it also "
                                   "hands it to the language optimiser, to measure first",
    "VIDEO_SHARE_SELECTORS": "exported by surfaces/video/, not by the root barrel; same measure first",
    "VIDEO_SOUND_SELECTORS": "exported by surfaces/video/, not by the root barrel; same measure first",
}


def test_every_shipped_catalogue_is_reachable_by_the_override_machinery():
    """A catalogue nobody registered cannot be version-overridden or clone-patched at all.

    Ten TikTok catalogues sat outside the map — the four video ones and all of publish — so the
    video counters could not be repaired by an override whichever way the A1/A2 call goes. This
    guard used to read the barrel only, and a catalogue the barrel does not export was invisible to
    it: `ACTIVITY_SELECTORS` (`surfaces/activity.py`) stayed out of reach while TikTok 47.0.3
    renamed its row (Pixel 6a, 2026-09-29). The facades are views over catalogues that ARE
    registered, and registering them is the bug this file also guards against.
    """
    from taktik.core.social_media.tiktok.ui import selectors as tiktok_selectors

    registered = {id(obj) for obj in TIKTOK_SELECTOR_DOMAINS.values()}
    unreachable = sorted(
        name for obj_id, name in _catalogues_defined_under(tiktok_selectors).items()
        if obj_id not in registered
    )
    assert unreachable == sorted(TIKTOK_CATALOGUES_OUT_OF_THE_MAP), (
        f"TikTok catalogues out of TIKTOK_SELECTOR_DOMAINS: {unreachable}; "
        f"listed with a reason: {sorted(TIKTOK_CATALOGUES_OUT_OF_THE_MAP)}"
    )


def test_every_instagram_catalogue_is_reachable():
    """Same guard for Instagram: nine catalogues (the post sub-catalogues among them) were out of
    reach of the version overrides and of the clone patch."""
    from dataclasses import is_dataclass

    from taktik.core.social_media.instagram.ui import selectors as instagram_barrel

    registered = {id(obj) for obj in INSTAGRAM_SELECTOR_DOMAINS.values()}
    unreachable = sorted(
        name for name in getattr(instagram_barrel, "__all__", [])
        if name.endswith("SELECTORS")
        and is_dataclass(getattr(instagram_barrel, name, None))
        and id(getattr(instagram_barrel, name)) not in registered
    )
    assert not unreachable, f"catalogues shipped but not registered in INSTAGRAM_SELECTOR_DOMAINS: {unreachable}"


def test_the_compat_map_and_the_language_optimiser_see_the_same_catalogues():
    """Two enumerations of the same objects must not drift — that is how ten went missing.

    The compat map keeps a literal spelling because its keys are a contract: override YAML
    addresses `domain.field`. The language optimiser derives its list from the barrel. This
    asserts they still describe the same set, so a catalogue added tomorrow is either reached by
    both or caught here.
    """
    from dataclasses import is_dataclass

    from taktik.core.social_media.tiktok.ui import selectors as barrel

    derived = set()
    for name in getattr(barrel, "__all__", ()):
        if not name.endswith("SELECTORS"):
            continue
        obj = getattr(barrel, name, None)
        if obj is not None and is_dataclass(obj):
            derived.add(id(obj))

    registered = {id(obj) for obj in TIKTOK_SELECTOR_DOMAINS.values()}
    assert registered == derived, (
        "the compat map and the barrel disagree on which catalogues exist — "
        f"{len(registered)} registered against {len(derived)} shipped"
    )
