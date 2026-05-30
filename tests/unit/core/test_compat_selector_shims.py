from taktik.core.compat import (
    SelectorNotFound as PublicSelectorNotFound,
    VersionedSelectorRegistry as PublicRegistry,
    create_registry as public_create_registry,
)
from taktik.core.compat.selector_registry import (
    SelectorNotFound as LegacySelectorNotFound,
    VersionedSelectorRegistry as LegacyRegistry,
)
from taktik.core.compat.selector_tracer import SelectorTracer as LegacySelectorTracer
from taktik.core.compat.selectors import (
    SelectorNotFound as ScopedSelectorNotFound,
    SelectorTracer as ScopedSelectorTracer,
    VersionedSelectorRegistry as ScopedRegistry,
    create_registry as scoped_create_registry,
)
from taktik.core.compat.setup import apply_version_overrides as legacy_apply_version_overrides
from taktik.core.compat.selectors.setup import (
    apply_version_overrides as scoped_apply_version_overrides,
)


def test_compat_public_facade_points_to_scoped_selector_owner():
    assert PublicRegistry is ScopedRegistry
    assert PublicSelectorNotFound is ScopedSelectorNotFound
    assert public_create_registry is scoped_create_registry


def test_legacy_selector_module_shims_resolve_to_scoped_owner():
    assert LegacyRegistry is ScopedRegistry
    assert LegacySelectorNotFound is ScopedSelectorNotFound
    assert LegacySelectorTracer is ScopedSelectorTracer
    assert legacy_apply_version_overrides is scoped_apply_version_overrides
