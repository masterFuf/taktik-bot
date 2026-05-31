from taktik.core.social_media.tiktok.services.publish.commit import (
    PublishCommitCallbacks,
    wait_for_publish_commit,
)


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def test_wait_for_publish_commit_settles_after_progress_badge_disappears():
    clock = FakeClock()
    progress_values = [12, 60, None, None]
    dismiss_calls = []

    def get_progress():
        return progress_values.pop(0) if progress_values else None

    callbacks = PublishCommitCallbacks(
        handle_publish_confirmation=lambda: False,
        dismiss_popups=lambda: dismiss_calls.append("dismiss"),
        get_progress_percent=get_progress,
        is_on_post_screen=lambda: False,
        has_success_indicator=lambda: False,
    )

    assert wait_for_publish_commit(
        callbacks,
        timeout=10.0,
        min_grace=0.0,
        settle_after_progress_gone=1.0,
        clock=clock.time,
        sleep=clock.sleep,
    )
    assert dismiss_calls


def test_wait_for_publish_commit_accepts_success_indicator():
    clock = FakeClock()
    callbacks = PublishCommitCallbacks(
        handle_publish_confirmation=lambda: False,
        dismiss_popups=lambda: None,
        get_progress_percent=lambda: None,
        is_on_post_screen=lambda: False,
        has_success_indicator=lambda: True,
    )

    assert wait_for_publish_commit(
        callbacks,
        timeout=10.0,
        min_grace=0.0,
        clock=clock.time,
        sleep=clock.sleep,
    )


def test_wait_for_publish_commit_times_out_when_caption_screen_never_leaves():
    clock = FakeClock()
    callbacks = PublishCommitCallbacks(
        handle_publish_confirmation=lambda: False,
        dismiss_popups=lambda: None,
        get_progress_percent=lambda: None,
        is_on_post_screen=lambda: True,
        has_success_indicator=lambda: False,
    )

    assert not wait_for_publish_commit(
        callbacks,
        timeout=2.0,
        min_grace=0.0,
        clock=clock.time,
        sleep=clock.sleep,
    )
