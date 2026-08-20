from __future__ import annotations

import logging
from pathlib import Path

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry

from app.core.settings import settings as global_settings
from app.core.spa_cache import prefetch_en_core_web_lg_from_data
from app.proxy.config_store import DEFAULT_CONFIG
from app.proxy.recognizers_custom import all_custom_recognizers

_log = logging.getLogger("shieldai")


def _disabled_builtin_entities(cfg: dict) -> set[str]:
    disabled: set[str] = set(cfg.get("disabled_builtin_entities", []) or [])
    if not cfg.get("credit_card_scanning", True):
        disabled.add("CREDIT_CARD")
    if not cfg.get("email_scanning", True):
        disabled.add("EMAIL_ADDRESS")
    return disabled


def _build_transformers_nlp_engine():
    """Build a Hugging Face transformers NLP engine, or None to fall back to spaCy."""
    try:
        from presidio_analyzer.nlp_engine import TransformersNlpEngine

        models = [
            {
                "lang_code": "en",
                "model_name": {
                    "spacy": "en_core_web_lg",
                    "transformers": global_settings.transformers_model,
                },
            }
        ]
        nlp = TransformersNlpEngine(models=models)
        nlp.load()
        _log.info(
            "[nlp] transformers engine active: %s", global_settings.transformers_model
        )
        return nlp
    except Exception as exc:  # noqa: BLE001 — never block startup on a heavy optional dep
        _log.warning(
            "[nlp] transformers engine requested but unavailable (%s); using spaCy.", exc
        )
        return None


def build_analyzer_engine(cfg: dict | None = None) -> AnalyzerEngine:
    cfg = cfg or DEFAULT_CONFIG
    prefetch_en_core_web_lg_from_data(Path("data"))

    use_transformers = str(getattr(global_settings, "nlp_engine", "spacy")).lower() == "transformers"
    nlp_engine = _build_transformers_nlp_engine() if use_transformers else None

    registry = RecognizerRegistry()
    if nlp_engine is not None:
        registry.load_predefined_recognizers(nlp_engine=nlp_engine)
    else:
        registry.load_predefined_recognizers()

    builtin_block = _disabled_builtin_entities(cfg)
    for rec in list(registry.recognizers):
        try:
            if any(ent in builtin_block for ent in rec.supported_entities):
                registry.remove_recognizer(rec.name)
        except KeyError:
            continue

    custom_cfg = cfg.get("custom_recognizers") or {}
    for r in all_custom_recognizers():
        entities = getattr(r, "supported_entities", None) or []
        entity = entities[0] if entities else getattr(r, "supported_entity", None)
        if not entity:
            continue
        if custom_cfg.get(entity, True):
            registry.add_recognizer(r)

    threshold = float(cfg.get("score_threshold", 0.5))
    engine_kwargs = dict(
        registry=registry,
        supported_languages=["en"],
        default_score_threshold=threshold,
    )
    if nlp_engine is not None:
        engine_kwargs["nlp_engine"] = nlp_engine
    return AnalyzerEngine(**engine_kwargs)
