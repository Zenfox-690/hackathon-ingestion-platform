import argparse
import sys

from exporter import export_public_catalog
from pipeline import IngestionPipeline
from startup_checks import validate_environment

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def run_pipeline(notify_telegram: bool = True, auto_export: bool = True):
    pipeline = IngestionPipeline(notify_telegram=notify_telegram, auto_export=auto_export)
    return pipeline.run()


def main():
    parser = argparse.ArgumentParser(description="Hackathon Ingestion Platform Runner")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram notifications")
    parser.add_argument("--no-export", action="store_true", help="Skip JSON catalog export")
    parser.add_argument(
        "--export-only", action="store_true", help="Only export current database to JSON catalog without scraping"
    )
    args = parser.parse_args()

    if args.export_only:
        print("[MAIN] Running export-only mode...")
        export_public_catalog()
        return

    validate_environment(require_bot_token=not args.no_telegram)
    run_pipeline(notify_telegram=not args.no_telegram, auto_export=not args.no_export)


if __name__ == "__main__":
    main()
