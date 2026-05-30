from taktik.core.database.instagram_hashtag_posts import InstagramHashtagPostService


class _FakeLocalDb:
    def __init__(self):
        self.is_processed_calls = []
        self.record_calls = []
        self.is_processed_result = False
        self.record_result = True

    def is_hashtag_post_processed(self, **kwargs):
        self.is_processed_calls.append(kwargs)
        return self.is_processed_result

    def record_processed_hashtag_post(self, **kwargs):
        self.record_calls.append(kwargs)
        return self.record_result


def test_is_processed_delegates_to_local_db(monkeypatch):
    fake_db = _FakeLocalDb()
    fake_db.is_processed_result = True
    monkeypatch.setattr(InstagramHashtagPostService, "_local_db", staticmethod(lambda: fake_db))

    ok = InstagramHashtagPostService.is_processed(
        hashtag="#travel",
        post_author="creator",
        post_caption_hash="abc123",
        account_id=7,
        hours_limit=24,
    )

    assert ok is True
    assert fake_db.is_processed_calls == [
        {
            "account_id": 7,
            "hashtag": "#travel",
            "post_author": "creator",
            "post_caption_hash": "abc123",
            "hours_limit": 24,
        }
    ]


def test_is_processed_requires_account_id():
    ok = InstagramHashtagPostService.is_processed(
        hashtag="travel",
        post_author="creator",
        account_id=None,
    )

    assert ok is False


def test_record_processed_delegates_to_local_db(monkeypatch):
    fake_db = _FakeLocalDb()
    monkeypatch.setattr(InstagramHashtagPostService, "_local_db", staticmethod(lambda: fake_db))

    ok = InstagramHashtagPostService.record_processed(
        hashtag="travel",
        post_author="creator",
        post_caption_hash="hash1",
        post_caption_preview="hello world",
        likes_count=321,
        comments_count=12,
        likers_processed=40,
        interactions_made=11,
        account_id=9,
    )

    assert ok is True
    assert fake_db.record_calls == [
        {
            "account_id": 9,
            "hashtag": "travel",
            "post_author": "creator",
            "post_caption_hash": "hash1",
            "post_caption_preview": "hello world",
            "likes_count": 321,
            "comments_count": 12,
            "likers_processed": 40,
            "interactions_made": 11,
        }
    ]


def test_record_processed_requires_account_id():
    ok = InstagramHashtagPostService.record_processed(
        hashtag="travel",
        post_author="creator",
        account_id=None,
    )

    assert ok is False


def test_generate_caption_hash_is_stable_and_normalized():
    left = InstagramHashtagPostService.generate_caption_hash("  Hello World  ")
    right = InstagramHashtagPostService.generate_caption_hash("hello world")

    assert left == right
    assert len(left) == 16


def test_generate_caption_hash_returns_empty_sentinel():
    assert InstagramHashtagPostService.generate_caption_hash("") == "empty"
