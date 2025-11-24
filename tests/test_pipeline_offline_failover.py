from pathlib import Path
from pipeline import enrich

def test_pipeline_offline(tmp_path):
    article = tmp_path / "a.md"
    article.write_text("# T\n\n## S\n\nText.")
    keywords = tmp_path / "k.txt"
    keywords.write_text("test")
    out = tmp_path / "out.md"
    final = enrich(str(article), str(keywords), str(out), model=None, offline=True, qa_mode="fallback")
    assert Path(final).exists()
