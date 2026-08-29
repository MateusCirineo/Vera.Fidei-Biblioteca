import unittest

from starlette.requests import Request

from api.routes.billing import _site_url
from core.config import Settings


class DomainConfigTests(unittest.TestCase):
    @staticmethod
    def _request(host: str) -> Request:
        return Request(
            {
                "type": "http",
                "method": "POST",
                "scheme": "https",
                "path": "/billing/checkout",
                "raw_path": b"/billing/checkout",
                "query_string": b"",
                "headers": [(b"host", host.encode("ascii"))],
                "client": ("127.0.0.1", 12345),
                "server": ("backend", 8000),
            }
        )

    def test_production_domains_are_allowed_without_duplicates(self):
        settings = Settings(
            _env_file=None,
            cors_origins=(
                " https://verafidei.com.br/,"
                "https://verafidei.oialfred.com,"
                "https://verafidei.com.br "
            ),
        )

        self.assertEqual(
            settings.parsed_cors_origins(),
            [
                "https://verafidei.com.br",
                "https://verafidei.oialfred.com",
            ],
        )

    def test_owned_domain_is_the_default_canonical_site(self):
        settings = Settings(_env_file=None)

        self.assertEqual(settings.site_url, "https://verafidei.com.br")
        self.assertEqual(
            settings.deploy_social_cards_public_base_url,
            "https://verafidei.com.br/social-cards",
        )
        self.assertIn(
            "https://verafidei.oialfred.com",
            settings.parsed_cors_origins(),
        )

    def test_billing_return_preserves_only_trusted_host_sessions(self):
        self.assertEqual(
            _site_url(self._request("verafidei.com.br")),
            "https://verafidei.com.br",
        )
        self.assertEqual(
            _site_url(self._request("www.verafidei.com.br:443")),
            "https://verafidei.com.br",
        )
        self.assertEqual(
            _site_url(self._request("verafidei.oialfred.com")),
            "https://verafidei.oialfred.com",
        )
        self.assertEqual(
            _site_url(self._request("verafidei.com.br.attacker.example")),
            _site_url(),
        )


if __name__ == "__main__":
    unittest.main()
