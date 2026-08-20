"""Prefer installing spaCy `en_core_web_lg` from `./data/` before AnalyzerEngine warmup."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def prefetch_en_core_web_lg_from_data(data_dir: str | Path = "data") -> None:
    root = Path(data_dir).resolve()
    try:
        import spacy  # noqa: F401

        spacy.load("en_core_web_lg")  # type: ignore[attr-defined]
        return
    except Exception:
        pass

    if not root.is_dir():
        return

    try:
        import spacy  # noqa: F401

        for candidate in sorted(root.glob("en_core_web_lg*")):
            if not candidate.is_dir():
                continue
            try:
                spacy.load(str(candidate))  # type: ignore[attr-defined]
                return
            except Exception:
                continue
    except Exception:
        pass

    whls = sorted(root.glob("en_core_web_lg*.whl"))
    if not whls:
        return

    wheel = str(whls[-1])
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-input",
            "--quiet",
            wheel,
        ],
        cwd=str(root.parent),
        check=False,
        timeout=600,
        capture_output=True,
    )

