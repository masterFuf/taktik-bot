"""Unit tests for the notification display-label cleaner."""

from taktik.core.social_media.instagram.workflows.management.notifications.classifier import clean_label


def test_new_follower_drops_trailing_action():
    assert clean_label("fufettecendree57 a commencé à vous suivre. 3 j Suivre en retour") \
        == "fufettecendree57 a commencé à vous suivre"
    assert clean_label("picture_life_forever a commencé à vous suivre. 1 sem Envoyer un message") \
        == "picture_life_forever a commencé à vous suivre"


def test_mention_drops_buttons_and_truncation():
    assert clean_label(
        "linstantmeliss a mentionné votre nom dans un commentaire : @sandra.lelit oh oui il faut y "
        "faire atte… suite 1 sem Bouton J'aime Répondre"
    ) == "linstantmeliss a mentionné votre nom dans un commentaire : @sandra.lelit oh oui il faut y faire atte"


def test_comment_drops_buttons():
    assert clean_label("fufettecendree57 a commenté : « .. » 3 j Bouton J'aime Répondre") \
        == "fufettecendree57 a commenté : « .. »"


def test_like_drops_only_time():
    assert clean_label("fufettecendree57 a aimé votre photo. 3 j") \
        == "fufettecendree57 a aimé votre photo"


def test_english_follow_back_and_more():
    assert clean_label("fufettecendree57 started following you. 3d Follow back") \
        == "fufettecendree57 started following you"
    assert clean_label("linstitut_elegance liked your comment: Félicitations pour cette belle… more 2d") \
        == "linstitut_elegance liked your comment: Félicitations pour cette belle"


def test_idempotent_and_clean_input_untouched():
    clean = "samir.akarioh a commencé à vous suivre"
    assert clean_label(clean) == clean
    assert clean_label(clean_label(clean)) == clean
