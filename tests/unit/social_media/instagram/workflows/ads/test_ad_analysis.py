"""Reading the collected ads — the AI pass, out of any run.

Capture happens on the phone at the speed of a flick; reading happens later on a machine
with nothing else to do. The tests below pin the two properties that make the pass cheap
rather than the prompt itself: it reads CREATIVES most-seen first, and it stamps everything
it touches so nothing is paid for twice.
"""

import json

import pytest

from taktik.core.social_media.instagram.workflows.ads import ad_analysis


class _Service:
    """Vision service double: records the calls, answers what it was told to."""

    def __init__(self, payload=None, raise_on=None):
        self.calls = []
        self._payload = payload if payload is not None else {"angle": "peur de rater"}
        self._raise_on = raise_on or set()

    def vision_json_completion(self, system, user, image_path, **kwargs):
        self.calls.append({'user': user, 'path': image_path})
        if len(self.calls) in self._raise_on:
            raise RuntimeError("model unavailable")
        return {"success": True, "payload": self._payload}


@pytest.fixture
def _corpus(monkeypatch):
    """A corpus in memory: what is pending, and what got stamped."""
    state = {'pending': [], 'saved': []}

    class _Service_:
        @staticmethod
        def pending_analysis(limit=20, platform="instagram"):
            return state['pending'][:limit]

        @staticmethod
        def save_analysis(creative_id, analysis):
            state['saved'].append((creative_id, analysis))
            return True

        @staticmethod
        def top_creatives(limit=50, platform="instagram"):
            return state.get('top', [])

    import taktik.core.database.instagram_feed_ads as db
    monkeypatch.setattr(db, 'InstagramFeedAdsService', _Service_)
    return state


def _creative(cid, seen=1, screenshot=b'\xff\xd8jpeg', advertiser='brand', ocr=None):
    return {'id': cid, 'times_seen': seen, 'screenshot': screenshot,
            'advertiser': advertiser, 'ocr_text': ocr, 'creative_hash': f'h{cid}'}


def test_no_ai_service_skips_instead_of_crashing(_corpus):
    _corpus['pending'] = [_creative(1)]
    report = ad_analysis.analyze_pending_ads(None, limit=5)
    assert report['analyzed'] == 0
    assert _corpus['saved'] == []


def test_each_analysed_creative_is_stamped(_corpus):
    _corpus['pending'] = [_creative(1), _creative(2)]
    service = _Service()

    report = ad_analysis.analyze_pending_ads(service, limit=5)

    assert report['analyzed'] == 2
    assert [cid for cid, _ in _corpus['saved']] == [1, 2]
    assert len(service.calls) == 2


def test_a_creative_without_a_screenshot_is_stamped_and_never_retried(_corpus):
    """Otherwise it comes back as pending on every pass, forever, and blocks the queue in
    front of creatives that could actually be read."""
    _corpus['pending'] = [_creative(1, screenshot=None)]
    service = _Service()

    report = ad_analysis.analyze_pending_ads(service, limit=5)

    assert service.calls == []            # nothing was paid for
    assert report['skipped'] == 1
    assert _corpus['saved'][0][0] == 1    # stamped anyway


def test_a_failing_call_does_not_stop_the_pass(_corpus):
    """One unreadable creative must not cost the nineteen behind it."""
    _corpus['pending'] = [_creative(1), _creative(2), _creative(3)]
    service = _Service(raise_on={2})

    report = ad_analysis.analyze_pending_ads(service, limit=5)

    assert report['analyzed'] == 2
    assert report['failed'] == 1
    assert [cid for cid, _ in _corpus['saved']] == [1, 3]


def test_the_ocr_text_is_offered_as_a_hint_not_as_the_truth(_corpus):
    """Tesseract mangles stylised type; the model must trust the picture over our reading."""
    _corpus['pending'] = [_creative(1, ocr='20% OFF CBD OIL')]
    service = _Service()

    ad_analysis.analyze_pending_ads(service, limit=1)

    prompt = service.calls[0]['user']
    assert '20% OFF CBD OIL' in prompt
    assert 'may be imperfect' in prompt


def test_the_advertiser_is_given_as_context(_corpus):
    _corpus['pending'] = [_creative(1, advertiser='sample_advertiser')]
    service = _Service()

    ad_analysis.analyze_pending_ads(service, limit=1)

    assert '@sample_advertiser' in service.calls[0]['user']


def test_the_queue_is_ordered_by_how_often_the_creative_runs():
    """The database, not the pass, owns that ordering — but it is the reason the corpus
    deduplicates at capture time, so it is pinned here too: a budget of twenty calls must go
    to the twenty ads actually running, not to twenty one-off impressions."""
    import inspect
    from taktik.core.database import instagram_feed_ads

    source = inspect.getsource(instagram_feed_ads.InstagramFeedAdsService.pending_analysis)
    assert 'ORDER BY times_seen DESC' in source
    assert 'ai_analyzed_at IS NULL' in source


def test_the_summary_reads_the_stored_analysis(_corpus):
    _corpus['top'] = [
        {'times_seen': 40, 'advertiser': 'sample_advertiser',
         'ai_analysis': json.dumps({'angle': 'douleur chronique'})},
        {'times_seen': 3, 'advertiser': 'other', 'ai_analysis': None},
    ]
    summary = ad_analysis.analysis_summary()
    assert '40x' in summary and 'sample_advertiser' in summary and 'douleur chronique' in summary
