"""Guard against treating ordinary product mentions as paid partnerships."""
import os
import unittest
from unittest.mock import patch

import update_social


class PartnershipDetectionTest(unittest.TestCase):
    def test_only_disclosed_posts_are_added_automatically(self):
        posts = [
            {"id": "1", "caption": "Loving our new dog bed", "permalink": "https://www.instagram.com/reel/ordinary/", "like_count": 10, "comments_count": 2},
            {"id": "2", "caption": "Tommy's new favorite treat #ad", "permalink": "https://www.instagram.com/reel/disclosed/", "like_count": 20, "comments_count": 4},
        ]
        def fake_graph(path, token, **params):
            return {"id": "123", "username": "tommythebernese", "followers_count": 42} if path == "123" else {"data": posts}
        data = {"followers": {}, "insights": {}, "sourceUpdatedAt": {}, "partnerships": []}
        with patch.dict(os.environ, {"META_ACCESS_TOKEN": "test", "INSTAGRAM_USER_ID": "123"}), patch.object(update_social, "graph", fake_graph):
            update_social.refresh_instagram(data, "2026-10-21T00:00:00Z")
        self.assertEqual(data["followers"]["instagram"], 42)
        self.assertEqual(data["insights"]["instagramRecentAverageInteractions"], 18)
        self.assertEqual([p["permalink"] for p in data["partnerships"]], ["https://www.instagram.com/reel/disclosed/"])


if __name__ == "__main__":
    unittest.main()
