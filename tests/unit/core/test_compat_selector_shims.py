from taktik.core.compat import (
    SelectorNotFound as PublicSelectorNotFound,
    VersionedSelectorRegistry as PublicRegistry,
    create_registry as public_create_registry,
)
from taktik.core.compat.selectors import (
    SelectorNotFound as ScopedSelectorNotFound,
    SelectorTracer as ScopedSelectorTracer,
    VersionedSelectorRegistry as ScopedRegistry,
    create_registry as scoped_create_registry,
)
from taktik.core.compat.selectors.setup import apply_version_overrides as scoped_apply_version_overrides


def test_compat_public_facade_points_to_scoped_selector_owner():
    assert PublicRegistry is ScopedRegistry
    assert PublicSelectorNotFound is ScopedSelectorNotFound
    assert public_create_registry is scoped_create_registry


def test_scoped_selector_package_exposes_runtime_owners():
    assert ScopedSelectorTracer.__name__ == "SelectorTracer"
    assert callable(scoped_apply_version_overrides)
