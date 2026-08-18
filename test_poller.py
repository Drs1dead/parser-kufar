"""Интервалы poller: VIP часто, обычные реже, без полной паузы после цикла."""
import unittest

from config import REGULAR_CHECK_INTERVAL, VIP_CHECK_INTERVAL
from poller import _poll_sleep_seconds, _seconds_until_due, _should_process_user


class PollerIntervalTests(unittest.TestCase):
    def test_new_user_is_due(self) -> None:
        user = {"role": "vip", "poll_last_vip": 0, "poll_last_regular": 0}
        self.assertTrue(_should_process_user(user, now=1_000.0))
        self.assertEqual(_seconds_until_due(user, 1_000.0), 0.0)

    def test_vip_not_due_before_interval(self) -> None:
        user = {"role": "vip", "poll_last_vip": 1_000.0}
        now = 1_000.0 + VIP_CHECK_INTERVAL - 10
        self.assertFalse(_should_process_user(user, now=now))
        self.assertAlmostEqual(_seconds_until_due(user, now), 10.0)

    def test_vip_due_after_interval(self) -> None:
        user = {"role": "vip", "poll_last_vip": 1_000.0}
        self.assertTrue(
            _should_process_user(user, now=1_000.0 + VIP_CHECK_INTERVAL)
        )

    def test_regular_due_after_configured_interval(self) -> None:
        user = {"role": "regular", "poll_last_regular": 1_000.0}
        self.assertFalse(
            _should_process_user(user, now=1_000.0 + REGULAR_CHECK_INTERVAL - 1)
        )
        self.assertTrue(
            _should_process_user(user, now=1_000.0 + REGULAR_CHECK_INTERVAL)
        )

    def test_sleep_capped_by_tick_when_vip_is_later(self) -> None:
        users = [
            {"role": "vip", "poll_last_vip": 1_000.0},
            {"role": "regular", "poll_last_regular": 1_000.0},
        ]
        now = 1_000.0 + 10
        delay = _poll_sleep_seconds(users, now, tick=10)
        self.assertAlmostEqual(delay, 10.0)

    def test_sleep_shortens_when_vip_due_sooner_than_tick(self) -> None:
        users = [{"role": "vip", "poll_last_vip": 1_000.0}]
        now = 1_000.0 + VIP_CHECK_INTERVAL - 3
        delay = _poll_sleep_seconds(users, now, tick=10)
        self.assertAlmostEqual(delay, 3.0)

    def test_sleep_does_not_busy_spin_when_due(self) -> None:
        users = [{"role": "vip", "poll_last_vip": 1_000.0}]
        delay = _poll_sleep_seconds(
            users, 1_000.0 + VIP_CHECK_INTERVAL + 10, tick=10
        )
        self.assertEqual(delay, 0.05)
