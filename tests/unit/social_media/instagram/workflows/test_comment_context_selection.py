"""A thread is material of three different trust levels, and mixing them is the bug.

The feature exists because a caption plus one vision reading is thin material, and a writer
given thin material compensates with style: replaying eighteen real comments on 2026-09-09,
six compared the post to a film and seventeen carried an emoji. The thread is where the
missing substance usually lives — an author answering a question about their own post — which
is why the author's replies are kept when every other reply is dropped.

The first justification written here was an invention, "j'adore cette idée de l'intégrer dans
des cakes" under a tofu post. The caption says "l'intégrer dans des sauces onctueuses ou des
cakes": the model was quoting the author, and the same replay found no invention at all. What
the thread adds is material, not protection.
"""

from taktik.core.social_media.instagram.workflows.common.comment_context import (
    ThreadSelection,
    context_overlap,
    select_thread_comments,
)


def rec(username, text, *, likes=0, is_reply=False, parent=None):
    return {"username": username, "text": text, "likes": likes,
            "is_reply": is_reply, "parent_username": parent}


# A real thread: one author clarification, two one-word compliments, one reader's plan.
TOFU_THREAD = [
    rec("chef_marie", "Non c'est du tofu soyeux fermente 24h, pas de la creme",
        likes=4, is_reply=True, parent="lea"),
    rec("lea", "Magnifique"),
    rec("paul", "Trop beau"),
    rec("sam", "La texture a l air incroyable, je vais tester avec du curcuma", likes=2),
]


def test_the_authors_own_reply_is_kept_as_a_fact():
    """The one channel that is evidence rather than opinion.

    An author clarifying their post almost always does it AS A REPLY to a commenter, so a rule
    that drops every reply would throw away the only factual material the thread carries — and
    that clarification exists in neither the caption nor the image.
    """
    selection = select_thread_comments(TOFU_THREAD, post_author="chef_marie")

    assert len(selection.author_replies) == 1
    assert "tofu soyeux" in selection.author_replies[0]["text"]
    assert selection.author_replies[0]["answers"] == "lea"


def test_a_reply_between_two_strangers_is_dropped():
    """Someone else's conversation is off-topic, and it carries copyable @mentions."""
    thread = [rec("tiers", "@lea oui carrement d accord avec toi la dessus",
                  is_reply=True, parent="lea")]
    selection = select_thread_comments(thread, post_author="chef_marie")

    assert selection.items == [] and selection.author_replies == []
    assert selection.dropped.get("reply_between_others") == 1


def test_short_praise_is_counted_and_never_listed():
    """Listing eight "magnifique" costs ~120 tokens AND teaches the banned register.

    Counted, the same information costs ~15 tokens and says the only useful thing: that reaction
    is already taken.
    """
    selection = select_thread_comments(TOFU_THREAD, post_author="chef_marie")

    assert selection.praise_count == 2
    assert selection.praise_samples == ["Magnifique", "Trop beau"]
    listed = " ".join(entry["text"] for entry in selection.items)
    assert "Magnifique" not in listed and "Trop beau" not in listed


def test_our_own_comment_is_recognised_even_without_a_handle():
    """Two nets, because the handle can be unresolvable while the text never is."""
    thread = [rec("someone", "Super recette du jour")]
    selection = select_thread_comments(
        thread, own_handle="", own_recent_texts=["Super recette du jour"]
    )

    assert selection.already_commented is True
    assert selection.items == []


def test_structural_spam_goes_without_a_word_list():
    """No vocabulary means no i18n debt and nothing to maintain per language."""
    thread = [
        rec("a", "Visitez www.spam.com/promo maintenant"),
        rec("b", "Appelez moi au 0612345678 tout de suite"),
        rec("c", "@x @y @z venez voir ca les amis"),
        rec("d", "TELLEMENT INCROYABLE CE POST VRAIMENT"),
        rec("e", "ouiiiiiiiiii carrement"),
    ]
    selection = select_thread_comments(thread)

    assert selection.items == []
    assert selection.dropped.get("spam") == 5


def test_a_foreign_script_is_dropped_before_the_language_filter():
    """`detect_text_language` only ever answers fr / en / None.

    A CJK, Cyrillic or Arabic comment would sail straight through the language check, eat the
    character budget and teach the model nothing — so the script test runs first.
    """
    thread = [rec("zhang", "这个看起来非常好吃我一定要试试看这个食谱今晚")]
    selection = select_thread_comments(thread, comment_lang="fr", base_lang="fr")

    assert selection.items == []
    assert selection.dropped.get("foreign_script") == 1


def test_screen_order_is_kept_and_likes_never_re_sort():
    """Instagram already ranks the thread; likes are parsed only intermittently.

    The fallback reader carries none at all, so re-sorting by likes would make two runs disagree
    about the same screen.
    """
    thread = [
        rec("a", "Premier commentaire avec de la substance dedans", likes=0),
        rec("b", "Deuxieme commentaire tout aussi substantiel ici", likes=99),
    ]
    selection = select_thread_comments(thread)

    assert [entry["text"][:7] for entry in selection.items] == ["Premier", "Deuxiem"]


def test_the_character_budget_stops_the_block_rather_than_the_run():
    """A thread of thirty long comments must not silently become the whole prompt."""
    # Distinct texts on purpose: identical ones would be deduplicated and never reach the
    # budget at all, which would make this test pass for the wrong reason.
    thread = [rec(f"u{i}", f"Commentaire numero {i} " + "avec de la matiere dedans " * 4)
              for i in range(14)]
    selection = select_thread_comments(thread)

    total = sum(len(entry["text"]) for entry in selection.items)
    assert total <= 900
    assert selection.truncated is True


def test_recurring_emoji_and_openers_of_this_thread_are_banned():
    """Aimed at the POST, where the anti-tic guard is aimed at the account.

    The repo already measured that a nominal ban does not hold — the sparkle stayed at 13.6 % of
    all emoji while nominally banned — and that a deterministic list does.
    """
    thread = [
        rec("a", "Cette lumiere est vraiment sublime ici 🌅"),
        rec("b", "Cette lumiere donne une ambiance folle 🌅"),
    ]
    selection = select_thread_comments(thread)

    assert "cette lumiere" in selection.banned_openers
    assert "🌅" in selection.banned_emoji


def test_nothing_readable_yields_an_empty_selection_not_an_error():
    """Every failure path lands here, and `has_material` is what the caller branches on."""
    for records in (None, [], [rec("a", "")], [rec("a", "ok")]):
        selection = select_thread_comments(records)
        assert isinstance(selection, ThreadSelection)
    assert select_thread_comments(None).has_material is False


def test_overlap_tells_an_echo_from_an_original_comment():
    """A comment that re-says the thread is worse than a bland one: it reads as a bot.

    Measured AFTER generation and never fed back in, so it stays an observation rather than a
    lever the model can optimise against.
    """
    selection = select_thread_comments(TOFU_THREAD, post_author="chef_marie")

    echo = context_overlap("La texture a l air incroyable vraiment", selection)
    original = context_overlap("Ce contraste de couleurs donne faim", selection)
    assert echo > 0.4 and original == 0.0
