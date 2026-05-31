from taktik.core.social_media.tiktok.services.publish.progress import (
    extract_percent_value,
    get_publish_progress_percent,
)


class FakeDumpDevice:
    def __init__(self, xml: str):
        self.xml = xml

    def dump_hierarchy(self, compressed: bool = False) -> str:
        return self.xml


def test_extract_percent_value_accepts_valid_percent_labels():
    assert extract_percent_value("81%") == 81
    assert extract_percent_value("  7 % ") == 7
    assert extract_percent_value("100%") == 100


def test_extract_percent_value_rejects_non_progress_labels():
    assert extract_percent_value(None) is None
    assert extract_percent_value("101%") is None
    assert extract_percent_value("Uploading") is None


def test_get_publish_progress_percent_reads_resource_id_badge():
    device = FakeDumpDevice(
        '<hierarchy><node resource-id="com.zhiliaoapp.musically:id/x44" text="42%" /></hierarchy>'
    )

    assert get_publish_progress_percent(device) == 42


def test_get_publish_progress_percent_reads_top_left_text_fallback():
    device = FakeDumpDevice(
        '<hierarchy><node text="58%" bounds="[12,80][66,120]" /></hierarchy>'
    )

    assert get_publish_progress_percent(device) == 58


def test_get_publish_progress_percent_ignores_large_or_far_text_nodes():
    device = FakeDumpDevice(
        '<hierarchy><node text="58%" bounds="[300,600][420,690]" /></hierarchy>'
    )

    assert get_publish_progress_percent(device) is None
