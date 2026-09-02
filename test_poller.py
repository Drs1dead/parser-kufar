"""Интервалы poller: VIP часто, обычные реже, без полной паузы после цикла."""
import unittest
from unittest.mock import AsyncMock, patch

import aiohttp

from config import FEED_REFRESH_SECONDS, REGULAR_CHECK_INTERVAL, VIP_CHECK_INTERVAL
from kufar_fetch import DEFAULT_HEADERS, enrich_ads_descriptions, _description_cache
from marketplace.keys import FetchKey
from poller import _fetch_catalog_groups, _fetch_cache, _poll_sleep_seconds, _seconds_until_due, _should_process_user


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
        self.assertEqual(delay, 1.0)


class PollerFetchCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_second_fetch_uses_cache_within_ttl(self) -> None:
        key: FetchKey = ("kufar", "phones", "7", "", ("iphone 15",), ("256",))
        groups = {key: [{"chat_id": 1}]}
        ads = [{"link": "https://www.kufar.by/item/1", "title": "iPhone"}]
        _fetch_cache.clear()

        mock_adapter = AsyncMock()
        mock_adapter.fetch_for_key = AsyncMock(return_value=ads)

        with patch("poller.get_adapter", return_value=mock_adapter):
            connector = aiohttp.TCPConnector(limit=8)
            async with aiohttp.ClientSession(
                headers=DEFAULT_HEADERS, connector=connector
            ) as session:
                ads1 = await _fetch_catalog_groups(groups, session=session)
                ads2 = await _fetch_catalog_groups(groups, session=session)
            self.assertEqual(len(ads1[key]), 1)
            self.assertEqual(len(ads2[key]), 1)
            self.assertEqual(mock_adapter.fetch_for_key.await_count, 1)

        cached = _fetch_cache.get(key)
        self.assertIsNotNone(cached)
        self.assertGreaterEqual(FEED_REFRESH_SECONDS, VIP_CHECK_INTERVAL)


class DescriptionCacheTests(unittest.IsolatedAsyncioTestCase):
    async def test_enrich_skips_http_when_link_cached(self) -> None:
        link = "https://www.kufar.by/item/cache-test"
        _description_cache.clear()
        ad = {"link": link, "description": ""}
        with patch(
            "kufar_fetch._fetch_description", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = "cached body"
            await enrich_ads_descriptions([ad])
            ad2 = {"link": link, "description": ""}
            await enrich_ads_descriptions([ad2])
            self.assertEqual(ad2["description"], "cached body")
            mock_fetch.assert_awaited_once()

    async def test_empty_description_not_cached(self) -> None:
        link = "https://www.kufar.by/item/empty-desc"
        _description_cache.clear()
        ad = {"link": link, "description": ""}
        with patch(
            "kufar_fetch._fetch_description", new_callable=AsyncMock
        ) as mock_fetch:
            mock_fetch.return_value = ""
            await enrich_ads_descriptions([ad])
            self.assertNotIn(link, _description_cache)
            await enrich_ads_descriptions([{"link": link, "description": ""}])
            self.assertEqual(mock_fetch.await_count, 2)