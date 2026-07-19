import os
import unittest
from unittest import mock

import adam_studio_app


class SeoRoutesTests(unittest.TestCase):
    def setUp(self):
        self.client = adam_studio_app.app.test_client()

    def test_sitemap_lists_public_pages_on_canonical_domain(self):
        with mock.patch.dict(
            os.environ,
            {"CANONICAL_SITE_URL": "https://www.adam-studio.net"},
        ):
            response = self.client.get("/sitemap.xml")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "application/xml")
        self.assertIn(b"<loc>https://www.adam-studio.net/</loc>", response.data)
        self.assertIn(
            b"<loc>https://www.adam-studio.net/shop</loc>", response.data
        )
        self.assertIn(
            b"<loc>https://www.adam-studio.net/help</loc>", response.data
        )

    def test_robots_allows_crawling_and_points_to_sitemap(self):
        with mock.patch.dict(
            os.environ,
            {"CANONICAL_SITE_URL": "https://www.adam-studio.net"},
        ):
            response = self.client.get("/robots.txt")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content_type, "text/plain")
        self.assertIn(b"User-agent: *", response.data)
        self.assertIn(b"Allow: /", response.data)
        self.assertIn(
            b"Sitemap: https://www.adam-studio.net/sitemap.xml",
            response.data,
        )


if __name__ == "__main__":
    unittest.main()
