from taktik.core.clone import OFFICIAL_PACKAGE
from taktik.core.clone.detection.detector import ORIGINAL_PACKAGES
from taktik.core.clone.packages.package_map import (
    CLONE_PREFIXES,
    get_clone_prefixes,
    get_original_package,
    get_package_variants,
)


def test_clone_package_map_is_shared_source_of_truth():
    assert OFFICIAL_PACKAGE == "com.instagram.android"
    assert get_original_package("instagram") == ORIGINAL_PACKAGES["instagram"]
    assert get_original_package("tiktok") == ORIGINAL_PACKAGES["tiktok"]
    assert get_clone_prefixes("instagram") == CLONE_PREFIXES["instagram"]
    assert get_clone_prefixes("tiktok") == CLONE_PREFIXES["tiktok"]
    assert "com.taktik.ig" in get_clone_prefixes("instagram")
    assert "com.taktik.tt" in get_clone_prefixes("tiktok")
    assert get_package_variants("tiktok")[0] == ORIGINAL_PACKAGES["tiktok"]
    assert "com.bytedance.trill" in get_package_variants("tiktok")
