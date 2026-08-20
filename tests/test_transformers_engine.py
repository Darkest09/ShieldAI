"""Integration test for the optional Hugging Face transformers NER backend.

Skipped automatically when torch / transformers / spacy-huggingface-pipelines
are not installed, so the lightweight (spaCy-only) setup still passes cleanly.
"""

import pytest

pytest.importorskip("torch")
pytest.importorskip("transformers")
pytest.importorskip("spacy_huggingface_pipelines")


def test_transformers_engine_detects_person_and_custom_entities() -> None:
    from app.core.settings import settings
    from app.core.presidio_setup import build_analyzer_engine
    from app.proxy.config_store import DEFAULT_CONFIG

    prev = settings.nlp_engine
    try:
        settings.nlp_engine = "transformers"
        engine = build_analyzer_engine(DEFAULT_CONFIG)
        text = (
            "Customer Sarita Shrestha, citizenship 27-01-78-12345, "
            "email sarita@nabilbank.com for KYC."
        )
        results = engine.analyze(text=text, language="en")
        types = {str(r.entity_type) for r in results}
        # Transformer NER should get the person; custom recognizers still fire.
        assert "PERSON" in types
        assert "NP_CITIZENSHIP_NUMBER" in types
        assert "EMAIL_ADDRESS" in types
    finally:
        settings.nlp_engine = prev
