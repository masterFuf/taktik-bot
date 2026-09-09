from taktik.core.social_media.account_management import (
    AccountCatalog,
    is_account_username,
    normalize_account_username,
)


def test_username_normalization_is_shared_and_backward_compatible():
    assert normalize_account_username("  @Creator.One ") == "creator.one"
    assert normalize_account_username(None) == ""


def test_username_validation_rejects_display_names_and_punctuation_only_values():
    assert is_account_username("creator_one") is True
    assert is_account_username("Creator One") is False
    assert is_account_username("..........") is False


def test_account_catalog_preserves_order_and_reports_normalized_ambiguity():
    catalog = AccountCatalog.from_values(
        ["@Creator.One", "second", "creator.one", "Display Name", "SECOND"]
    )

    assert catalog.accounts == ("creator.one", "second")
    assert catalog.ambiguous == ("creator.one", "second")
    assert catalog.contains("@SECOND") is True
    assert catalog.is_ambiguous("Creator.One") is True


def test_account_catalog_respects_platform_length_limit():
    catalog = AccountCatalog.from_values(["a" * 24, "b" * 25], max_length=24)

    assert catalog.accounts == ("a" * 24,)
    assert catalog.ambiguous == ()
