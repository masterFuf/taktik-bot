"""The anonymizer keeps the screen and drops the people.

Run on a real fixture (TikTok 43.1.4, the For You feed), into which invented personal data is
written the way a capture carries it: a display name, a handle, a phone number, a clock, a date.
"""

import sys

from lxml import etree
from unit.paths import CORE

sys.path.insert(0, str(CORE / "scripts/lab"))

import anonymize_dump  # noqa: E402

FIXTURE = CORE / "tests/unit/social_media/tiktok/fixtures/tt4314_fr_for_you_video.xml"
TITLE = "com.zhiliaoapp.musically:id/title"
DESC = "com.zhiliaoapp.musically:id/desc"


def _capture():
    """The fixture, carrying what a real capture would."""
    root = etree.fromstring(FIXTURE.read_bytes())
    root.xpath(f'//node[@resource-id="{TITLE}"]')[0].set("text", "jeanne.martin_75")
    root.xpath(f'//node[@resource-id="{DESC}"]')[0].set(
        "text", "Jeanne Martin, appelle au 06 12 34 56 78 avant 14:32 le 26/09/2026 #voyage")
    root.xpath('//node[@content-desc="Profil"]')[0].set("content-desc", "Profil de jeanne.martin_75")
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def _root(xml):
    return etree.fromstring(xml)


def _values(xml):
    return anonymize_dump.read_values(xml)


def test_the_tree_is_untouched():
    before, after = _root(_capture()), _root(anonymize_dump.anonymize(_capture()))

    shape = [(n.tag, n.get("resource-id"), n.get("class"), n.get("bounds"), n.get("clickable"))
             for n in before.iter()]
    assert shape == [(n.tag, n.get("resource-id"), n.get("class"), n.get("bounds"), n.get("clickable"))
                     for n in after.iter()]


def test_the_app_labels_stay():
    values = _values(anonymize_dump.anonymize(_capture()))

    for label in ("Pour toi", "Accueil", "Suivis", "Attribuer un « J'aime » à la vidéo. 73 « J'aime »"):
        assert label in values


def test_the_people_go():
    text = " ".join(_values(anonymize_dump.anonymize(_capture())))

    for personal in ("jeanne", "Jeanne", "Martin", "voyage", "06 12 34 56 78", "14:32", "26/09/2026"):
        assert personal not in text
    assert "00 00 00 00 00" in text and "12:00" in text and "01/01/2000" in text


def test_the_same_person_gets_the_same_name_everywhere():
    after = _root(anonymize_dump.anonymize(_capture()))

    handle = after.xpath(f'//node[@resource-id="{TITLE}"]')[0].get("text")
    assert handle.startswith("user_")
    assert f"Profil de {handle}" in _values(etree.tostring(after))


def test_a_kept_word_can_be_dropped():
    values = _values(anonymize_dump.anonymize(_capture(), drop=("Boutique",)))

    assert "Boutique" not in values and "Pour toi" in values


def test_the_command_writes_the_fixture_and_lists_what_is_left(tmp_path, capsys):
    source, target = tmp_path / "raw.xml", tmp_path / "fixture.xml"
    source.write_bytes(_capture())

    assert anonymize_dump.main([str(source), str(target)]) == 0

    assert "Pour toi" in _values(target.read_bytes())
    assert "Pour toi" in capsys.readouterr().out


def _capture_of(handle):
    """The same screen, its title carrying another handle (the next capture of a scene)."""
    root = etree.fromstring(_capture())
    root.xpath(f'//node[@resource-id="{TITLE}"]')[0].set("text", handle)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


def test_a_scene_keeps_one_name_per_person_across_its_captures():
    # Before the gesture the title shows jeanne, after it paul, whom the description of the first
    # capture already names: paul must read the same in both, or a test pairing them breaks.
    first = etree.fromstring(_capture())
    first.xpath(f'//node[@resource-id="{DESC}"]')[0].set("text", "avec paul.durand_33")
    before, after = anonymize_dump.anonymize_series(
        [etree.tostring(first, encoding="UTF-8"), _capture_of("paul.durand_33")])

    in_before = _root(before).xpath(f'//node[@resource-id="{DESC}"]')[0].get("text").split()[-1]
    in_after = _root(after).xpath(f'//node[@resource-id="{TITLE}"]')[0].get("text")
    assert in_before == in_after and in_after.startswith("user_")


def test_the_command_takes_the_captures_of_a_scene_in_pairs(tmp_path):
    sources = [tmp_path / "before.xml", tmp_path / "after.xml"]
    targets = [tmp_path / "before_fixture.xml", tmp_path / "after_fixture.xml"]
    sources[0].write_bytes(_capture())
    sources[1].write_bytes(_capture_of("jeanne.martin_75"))

    assert anonymize_dump.main([str(sources[0]), str(targets[0]), str(sources[1]), str(targets[1]), "--quiet"]) == 0

    title = f'//node[@resource-id="{TITLE}"]'
    assert (_root(targets[0].read_bytes()).xpath(title)[0].get("text")
            == _root(targets[1].read_bytes()).xpath(title)[0].get("text"))
