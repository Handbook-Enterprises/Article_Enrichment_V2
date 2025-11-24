import os
import sys
import argparse
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

"""
CLI entry point for the content enrichment pipeline.
This script is located under scripts/ and ensures src/ is on sys.path.
"""

# Ensure src/ is importable for the "src layout"
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from db.data_access import (
    load_article,
    load_keywords,
    load_brand_rules,
    load_media_db,
    load_links_db,
)
from pipeline import enrich


def setup_logging():
    # Ensure logs directory exists
    logs_dir = ROOT_DIR / "logs"
    try:
        logs_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    # Timestamped log file per run
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"run_{ts}.log"

    # Configure root logger with console + file handlers
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    # Clear any pre-existing handlers to avoid duplicate logs
    logger.handlers.clear()

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler
    try:
        fh = logging.FileHandler(str(log_file), encoding="utf-8")
        fh.setLevel(logging.INFO)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
        logging.info(f"Logging to file: {log_file}")
    except Exception as e:
        logging.warning(f"Could not create log file at {log_file}: {e}")


def main():
    setup_logging()

    # Load environment variables from project root and config/.env,
    # then manually parse as a fallback to ensure availability in all shells.
    config_env = ROOT_DIR / "config" / ".env"
    try:
        # Load from current working dir (project root) if present
        load_dotenv(override=True)
        # Load from config/.env if present
        if config_env.exists():
            load_dotenv(dotenv_path=config_env, override=True)
    except Exception:
        pass
    # Manual fallback: parse .env files if the key still isn't present
    if not (os.getenv("OPENROUTER_API_KEY") or "").strip():
        for env_path in [ROOT_DIR / ".env", config_env]:
            if env_path.exists():
                try:
                    for line in env_path.read_text(encoding="utf-8").splitlines():
                        s = line.strip()
                        if not s or s.startswith("#"):
                            continue
                        if "=" in s:
                            k, v = s.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            if k and v:
                                os.environ.setdefault(k, v)
                except Exception:
                    # Ignore parse errors and continue
                    pass

    parser = argparse.ArgumentParser(description="LLM-powered content enrichment for Markdown articles")
    parser.add_argument("--article_path", required=True, help="Path to input Markdown article")
    parser.add_argument("--keywords_path", required=True, help="Path to keywords .txt (one per line)")
     # Static paths for resources (media.db, links.db, brand_rules.txt)
    media_db_path = ROOT_DIR / "db" / "media.db"
    links_db_path = ROOT_DIR / "db" / "links.db"
    brand_rules_path = ROOT_DIR / "docs" / "brand_rules.txt"
    
    parser.add_argument("--out_path", default=None, help="Path to write enriched Markdown")
    parser.add_argument("--model", default=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"), help="OpenRouter model id")
    parser.add_argument("--offline", action="store_true", help="Disable LLM calls; use deterministic fallback")
    parser.add_argument("--qa_mode", default=os.getenv("QA_MODE", "auto"), choices=["auto","ai","fallback"], help="QA verification mode")

    args = parser.parse_args()
    logging.info(
              f"Starting enrichment | article={args.article_path} | keywords={args.keywords_path} | model={args.model} | offline_flag={'true' if args.offline else 'false'}"
    )
    logging.info(
        f"Using static paths | media_db={media_db_path} | links_db={links_db_path} | brand_rules={brand_rules_path}"
    )

    final_path = enrich(
        article_path=args.article_path,
        keywords_path=args.keywords_path,
        out_path=args.out_path,
        model=args.model,
        offline=args.offline,
        qa_mode=args.qa_mode,
    )
    logging.info(f"Done | output={final_path}")


if __name__ == "__main__":
    main()
