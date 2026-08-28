from __future__ import annotations

import unittest

from api.routes import pdfs
from core.deps import get_current_user
from core.plans import PLAN_ORDER, has_feature


class PdfAccessPolicyTests(unittest.TestCase):
    def test_pdf_route_requires_login_without_requiring_a_paid_plan(self) -> None:
        route = next(route for route in pdfs.router.routes if route.path == "/{file_id}")
        dependencies = [dependency.call for dependency in route.dependant.dependencies]

        self.assertEqual(dependencies, [get_current_user])

    def test_every_valid_plan_includes_digitized_pdfs(self) -> None:
        for plan in PLAN_ORDER:
            with self.subTest(plan=plan):
                self.assertTrue(has_feature(plan, "digitized_pdfs"))


if __name__ == "__main__":
    unittest.main()
