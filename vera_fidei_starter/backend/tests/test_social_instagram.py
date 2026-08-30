from __future__ import annotations

import unittest
import copy
import json
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageDraw

from app.agents.base import PipelineContext
from app.agents.orchestrator import OrchestratorAgent
from app.services.dispatcher import PipelineDispatcher
from app.social.carousel import (
    CANVAS_SIZE,
    _COVER_REFERENCE,
    _CTA_REFERENCE,
    _HIGHLIGHT,
    _PAGE_TEMPLATE,
    CarouselContent,
    render_carousel,
)
from app.social.content_guard import (
    extract_coherent_passage,
    is_manually_blocked,
    looks_like_editorial_noise,
    quote_fingerprint,
    validate_candidate,
)
from app.social.post_model import SocialPostCandidate
from app.social.instagram_publish import publish_carousel_to_instagram
from app.social.instagram_publish import PublicationBlocked
from app.social.ledger import SocialLedger
from app.social.daily_card import _pick_portuguese_text
from app.social.package import publish_package
from app.social.promo_post import (
    KEYWORD_RGB,
    LaunchCampaign,
    load_launch_campaign,
    render_promo_carousel,
    validate_launch_campaign,
)
from core.config import settings


_QUOTE = (
    "Ele é o meu bem, e eu exulto em sua honra por todos os bens que constituem a minha "
    "existência desde a infância. Meu pecado era não procurar nele, e sim nas suas criaturas — "
    "isto é, em mim mesmo e nos outros — os prazeres, as honras e a verdade. Eu me precipitava "
    "assim na dor, na confusão e no erro. Graças a ti, ó minha doçura, minha glória, minha "
    "confiança, meu Deus, pelos dons que me deste. Conserva-os, pois. E assim me conservarás."
)


def _candidate() -> SocialPostCandidate:
    value = SocialPostCandidate(
        chunk_id=13261,
        book_id=44,
        book_file_id=215,
        author="Santo Agostinho de Hipona",
        work_title="Confissões",
        quote=_QUOTE,
        original_text=_QUOTE,
        language="pt",
        collection="PT",
        volume=10,
        edition_label="Paulus",
        pdf_page=34,
        author_dates="354–430",
        century="séculos IV–V",
        highlight_terms=["Deus", "pecado", "verdade"],
    )
    value.source_fingerprint = quote_fingerprint(
        chunk_id=value.chunk_id,
        author=value.author,
        work_title=value.work_title,
        quote=value.quote,
    )
    return value


def _source_page() -> bytes:
    image = Image.new("RGB", (1200, 1800), "white")
    draw = ImageDraw.Draw(image)
    for row in range(24):
        draw.text((80, 80 + row * 60), "CONFESSIONES — fonte da página 34", fill="black")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ContentGuardTests(unittest.TestCase):
    def test_social_copy_never_uses_unverified_legacy_translation(self) -> None:
        from types import SimpleNamespace

        latin_chunk = SimpleNamespace(book=SimpleNamespace(language="la"))
        portuguese_chunk = SimpleNamespace(book=SimpleNamespace(language="pt"))
        self.assertEqual(_pick_portuguese_text(latin_chunk, "Verbum caro factum est."), ("", ""))
        self.assertEqual(
            _pick_portuguese_text(portuguese_chunk, "O Verbo se fez carne."),
            ("O Verbo se fez carne.", ""),
        )

    def test_rejects_table_of_contents(self) -> None:
        toc = "Índice " + " ".join(f"SALMO {n} {100+n}" for n in range(20)) + ". Fim."
        self.assertTrue(looks_like_editorial_noise(toc))
        self.assertEqual(extract_coherent_passage(toc), "")

    def test_blocks_already_published_ambrose_excerpt(self) -> None:
        self.assertTrue(
            is_manually_blocked(
                "Tens os apóstolos por próximos, tens os mártires por próximos."
            )
        )

    def test_author_mismatch_is_fatal(self) -> None:
        report = validate_candidate(_candidate(), expected_author="Santo Ambrósio de Milão")
        self.assertFalse(report.ok)
        self.assertTrue(any("autor solicitado" in error for error in report.errors))

    def test_coherent_candidate_passes(self) -> None:
        report = validate_candidate(_candidate(), expected_author="Santo Agostinho")
        self.assertTrue(report.ok, report.errors)


class VisualPipelineTests(unittest.TestCase):
    def test_homologated_brand_contract(self) -> None:
        self.assertEqual(CANVAS_SIZE, (1856, 2304))
        self.assertEqual(_HIGHLIGHT, (102, 29, 20))
        self.assertEqual(Path(settings.social_body_font_path).name.upper(), "ARLRDBD.TTF")
        for asset in (_PAGE_TEMPLATE, _COVER_REFERENCE, _CTA_REFERENCE):
            self.assertTrue(asset.is_file(), asset)

    def test_renders_three_reference_sized_slides(self) -> None:
        portrait = (
            Path(__file__).resolve().parents[1]
            / "app"
            / "social"
            / "assets"
            / "portraits"
            / "Santo Agostinho de Hipona.jpg"
        ).read_bytes()
        slides = render_carousel(
            CarouselContent(
                candidate=_candidate(),
                portrait_bytes=portrait,
                pdf_page_bytes=_source_page(),
                pdf_title_page_bytes=_source_page(),
                pdf_excerpt_bytes=[_source_page()],
            )
        )
        self.assertEqual(len(slides), 3)
        for payload in slides:
            with Image.open(BytesIO(payload)) as image:
                self.assertEqual(image.size, CANVAS_SIZE)

    def test_orchestrator_routes_instagram_to_social_agents(self) -> None:
        ctx = PipelineContext("Gerar carrossel para Instagram")
        result = OrchestratorAgent().run(ctx)
        self.assertEqual(result.status, "ok")
        self.assertIn("social_consistency_agent", ctx.mission["execution_order"])
        self.assertIn("social_copy_agent", ctx.mission["execution_order"])
        self.assertEqual(ctx.mission["execution_order"][-1], "social_publish_agent")

    def test_launch_campaign_uses_same_agents_and_distinct_scope(self) -> None:
        ctx = PipelineContext("Gerar carrossel de lançamento para Instagram")
        ctx.findings["social_options"] = {"campaign_kind": "launch"}
        result = OrchestratorAgent().run(ctx)
        self.assertEqual(result.status, "ok")
        self.assertEqual(
            ctx.mission["execution_order"],
            [
                "planner",
                "social_source_agent",
                "social_consistency_agent",
                "social_copy_agent",
                "social_art_agent",
                "social_approval_agent",
                "social_publish_agent",
            ],
        )
        self.assertIn("manifesto versionado", " ".join(ctx.mission["scope"]))


class LaunchCampaignTests(unittest.TestCase):
    def test_manifest_is_factual_and_renders_exact_contract(self) -> None:
        campaign = load_launch_campaign()
        report = validate_launch_campaign(campaign)
        self.assertTrue(report.ok, report.errors)
        self.assertEqual(KEYWORD_RGB, (102, 29, 20))
        slides = render_promo_carousel(campaign)
        self.assertEqual(len(slides), 3)
        for payload in slides:
            with Image.open(BytesIO(payload)) as image:
                self.assertEqual(image.size, (1856, 2304))

    def test_manifest_blocks_old_prelaunch_and_forbidden_claims(self) -> None:
        payload = copy.deepcopy(load_launch_campaign().payload)
        payload["caption"] += " Em breve: verificação infalível."
        report = validate_launch_campaign(LaunchCampaign(payload))
        self.assertFalse(report.ok)
        self.assertTrue(any("em breve" in error for error in report.errors))
        self.assertTrue(any("verificação infalível" in error for error in report.errors))

    @patch("app.social.package.upload_card")
    @patch("app.social.package.ensure_publication_enabled")
    def test_full_launch_pipeline_stays_preview_only(self, _gate, upload_card) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "output"
            ledger = Path(temp_dir) / "ledger.jsonl"
            with patch.object(settings, "social_output_dir", str(output)), patch.object(
                settings, "social_ledger_path", str(ledger)
            ):
                ctx = PipelineDispatcher().run(
                    "Gerar prévia do carrossel oficial de lançamento da PWA no Instagram",
                    initial_findings={
                        "social_options": {
                            "campaign_kind": "launch",
                            "publish_requested": False,
                        }
                    },
                )
                package = Path(ctx.findings["social_package"])
                manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["content_kind"], "launch")
                self.assertFalse(manifest["publishable"])
                self.assertFalse(manifest["published"])
                self.assertEqual(len(manifest["artifacts"]), 3)
                self.assertEqual(ctx.history[-2].status, "awaiting_approval")
                self.assertEqual(ctx.history[-1].status, "skipped")
                with self.assertRaisesRegex(ValueError, "não foi homologada"):
                    publish_package(package, SocialLedger(ledger))
        upload_card.assert_not_called()


class InstagramApiWorkflowTests(unittest.TestCase):
    def test_legacy_credential_override_is_disabled_by_default(self) -> None:
        self.assertFalse(settings.instagram_allow_exposed_credentials_once)

    @patch("app.social.package.upload_card")
    @patch(
        "app.social.package.ensure_publication_enabled",
        side_effect=PublicationBlocked("credencial não liberada"),
    )
    def test_disabled_publication_stops_before_upload(self, _gate, upload_card) -> None:
        with self.assertRaises(PublicationBlocked):
            publish_package("pacote-inexistente", SocialLedger("ledger-inexistente.jsonl"))
        upload_card.assert_not_called()

    @patch("app.social.instagram_publish._wait_until_ready")
    @patch("app.social.instagram_publish._graph_request")
    @patch("app.social.instagram_publish._credentials", return_value=("token", "account"))
    @patch("app.social.instagram_publish._publication_gate")
    def test_carousel_creates_children_parent_and_publish(
        self, _gate, _credentials, graph_request, wait_until_ready
    ) -> None:
        graph_request.side_effect = [
            {"id": "child-1"},
            {"id": "child-2"},
            {"id": "child-3"},
            {"id": "parent"},
            {"id": "remote-media"},
        ]
        media_id = publish_carousel_to_instagram(
            ["https://example.test/1.png", "https://example.test/2.png", "https://example.test/3.png"],
            "Legenda rastreável",
        )
        self.assertEqual(media_id, "remote-media")
        self.assertEqual(graph_request.call_count, 5)
        self.assertEqual(wait_until_ready.call_count, 4)


if __name__ == "__main__":
    unittest.main()
