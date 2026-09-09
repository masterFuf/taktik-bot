"""The anchor is the contract that keeps a comment specific WITHOUT letting it drift.

The problem it solves was measured on 2026-09-09 over eighteen real posts, replayed three ways.
The production prompt reaches for STYLE when the material is thin: six of the eighteen comments
compared the post to a film, and seventeen carried an emoji. Relaxing the rules to allow a plain
reaction fixed the style but took the bland count from 1 to 8 of 18 — a register offered as an
equal option becomes the default one. Under the contract, the model writes BOTH registers and
states, in `anchor`, the words it reacted to; code checks that claim and picks. Same corpus:
2 bland of 18, no cinema metaphor.

WHAT THESE TESTS ARE NOT. The feature was first justified by an apparent invention — "des cakes"
under a tofu post. The caption turned out to say "l'intégrer dans des sauces onctueuses ou des
cakes", so the model was quoting the author, and the same replay found no invention at all. The
check below is a cheap backstop on a claim, not a hallucination shield, and these tests pin its
edges rather than a bug it has caught.
"""

from taktik.core.social_media.instagram.workflows.common.comment_context import (
    ThreadSelection,
    anchor_material,
    select_thread_comments,
    verify_anchor,
)

CAPTION = "Recette du soir, tout est fait maison #tofusoyeux"
VISION = "A plate of silken tofu with a creamy sauce, a stuffed melon and a pasta dish"
THREAD = [
    {"username": "chef_marie", "text": "Non c'est du tofu soyeux fermente 24h, pas de la creme",
     "is_reply": True, "parent_username": "lea", "likes": 4},
    {"username": "sam", "text": "La texture a l air incroyable, je vais tester avec du curcuma",
     "is_reply": False, "parent_username": None, "likes": 2},
]


def material():
    selection = select_thread_comments(THREAD, post_author="chef_marie")
    return anchor_material(caption=CAPTION, vision=VISION, selection=selection)


def test_something_absent_from_the_material_is_rejected():
    """The whole point of the check, on a thing genuinely nowhere in this post."""
    for absent in ("la terrasse en rooftop", "ton chien", "le barbecue"):
        assert verify_anchor(absent, material()) is False, absent


def test_the_authors_own_clarification_is_a_valid_anchor():
    """A reply is the only channel that turns a guess into a fact, so it must anchor.

    Without it "fermente 24h" is unsayable: it is in neither the caption nor the image.
    """
    assert verify_anchor("le tofu soyeux fermente", material()) is True


def test_a_paraphrase_of_the_vision_still_anchors():
    """"cremeuse" against "creamy" — the vision reads in English and the comment writes in French.

    Demanding identity across that gap would reject honest anchors and push every post to the
    fallback, which is the blandness this design exists to avoid.
    """
    assert verify_anchor("la sauce cremeuse", material()) is True


def test_the_three_measured_false_alarms_all_pass_now():
    """Every rejection this check has ever produced was wrong, and these are the three.

    Two full replays of eighteen real posts on 2026-09-09 rejected three anchors and caught zero
    fabrications. Each rejection came from a different piece of over-strictness, and each cost a
    specific comment that got downgraded to a plain one. They are pinned together because they
    are one finding: the check must fail a FABRICATION, and tolerate a clumsy copy.
    """
    # A caption that is only a handle. `_words` deleted mentions whole, leaving nothing.
    assert verify_anchor("@shame", anchor_material(
        caption="@shame", vision="a black-and-white concert photograph")) is True

    # A caption that is only an emoji. `_strip_marks` deleted it, leaving nothing.
    assert verify_anchor("\u26f1\ufe0f", anchor_material(
        caption="\u26f1\ufe0f", vision="a waterfront cafe with a bright orange umbrella")) is True

    # A real caption phrase copied with one letter missing ("vdenost" for "vdecnost"). At a 0.6
    # coverage threshold a two-word anchor needed BOTH words, so one typo failed the whole claim.
    assert verify_anchor("nekonecna vdenost", anchor_material(
        caption="Nekonecna zima, nekonecna vdecnost. Diky za kazdy den na prkne.",
        vision="a snowboarder at Niseko")) is True


def test_a_hashtag_in_the_caption_is_the_authors_own_word():
    """A hashtag is the author writing about their own post — "#metz" under a photo of Metz."""
    assert verify_anchor("#tofusoyeux", material()) is True


def test_half_a_fabricated_anchor_is_still_a_fabrication():
    """The floor the loosening must not cross: naming one real thing does not license the rest.

    "le tofu sur la terrasse en rooftop" is one word of truth in three, and there is no terrace.
    """
    assert verify_anchor("le tofu sur la terrasse en rooftop", material()) is False


def test_an_emoji_the_author_never_used_is_rejected():
    """Emoji count as material, which must not turn every emoji into a free pass."""
    umbrella = anchor_material(caption="\u26f1\ufe0f", vision="a waterfront cafe")
    assert verify_anchor("\U0001f6f9", umbrella) is False


def test_a_strangers_comment_is_not_material():
    """The load-bearing asymmetry: the thread informs the model, it never grounds a claim.

    Anchoring on "du curcuma" would launder a reader's PLAN into our own observation and
    congratulate the author for turmeric they never used.
    """
    assert "curcuma" in THREAD[1]["text"]
    assert verify_anchor("le curcuma", material()) is False


def test_an_anchor_made_of_stopwords_is_not_an_anchor():
    """"la photo" matches every post ever written, so it certifies nothing."""
    for empty in ("la photo", "cette image", "le post", "ce que tu fais"):
        assert verify_anchor(empty, material()) is False, empty


def test_one_content_word_is_enough():
    """Real anchors are often a single noun — "melon", "solstice". The stopword list, not a word
    count, is what separates those from "la photo"."""
    assert verify_anchor("melon", material()) is True


def test_no_material_rejects_every_anchor():
    """A vision failure must not silently license a claim: with nothing read, nothing is
    provable, and the comment falls back to the safe register."""
    for anchor in ("le tofu soyeux", "la terrasse", "la lumiere"):
        assert verify_anchor(anchor, "") is False, anchor


def test_material_ignores_a_selection_that_read_nothing():
    """Every device failure lands on an empty ThreadSelection, which must behave as absent."""
    assert anchor_material(caption=CAPTION, vision=VISION, selection=ThreadSelection()) == (
        anchor_material(caption=CAPTION, vision=VISION)
    )
