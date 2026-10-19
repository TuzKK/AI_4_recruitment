from pathlib import Path

from matching_eval.samples import extract_pdf_text, load_manifest

SAMPLE_ROOT = Path(__file__).resolve().parents[2] / "Samples_for_optimization"


def test_curated_manifest_contains_unique_verified_samples():
    samples = load_manifest(SAMPLE_ROOT)
    assert len(samples) == 8
    assert sum(sample["label"] == "high_match" for sample in samples) == 2
    assert len({sample["sha256"] for sample in samples}) == 8


def test_pdf_extraction_returns_real_resume_text():
    text = extract_pdf_text(SAMPLE_ROOT / "admitted" / "A001.pdf")
    assert len(text) > 200
    assert "\f" not in text


def test_pdf_extraction_works_without_poppler(monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise FileNotFoundError("pdftotext")

    monkeypatch.setattr("matching_eval.samples.subprocess.run", unavailable)
    text = extract_pdf_text(SAMPLE_ROOT / "admitted" / "A001.pdf")
    assert len(text) > 200
