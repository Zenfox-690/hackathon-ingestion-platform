import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import db.store as store
from bot.notifier import send_message
from exporter import export_public_catalog
from fetcher.base import BaseFetcher
from fetcher.devfolio import DevfolioFetcher
from fetcher.devpost import DevpostFetcher
from fetcher.unstop import UnstopFetcher
from logs.logger import log
from models.hackathon import Hackathon


@dataclass
class SourceRunMetric:
    source_name: str
    fetched: int = 0
    accepted: int = 0
    rejected: int = 0
    duplicates: int = 0
    new: int = 0
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class PipelineRunSummary:
    total_fetched: int = 0
    total_accepted: int = 0
    total_rejected: int = 0
    total_duplicates: int = 0
    total_new: int = 0
    failed_sources: List[str] = field(default_factory=list)
    sources: Dict[str, SourceRunMetric] = field(default_factory=dict)
    duration_seconds: float = 0.0
    export_successful: bool = False

    def print_summary(self):
        print("\n" + "=" * 50)
        print("         INGESTION PIPELINE RUN SUMMARY")
        print("=" * 50)
        print(f"Total Duration:     {self.duration_seconds:.2f}s")
        print(f"Total Fetched:      {self.total_fetched}")
        print(f"Total Accepted:     {self.total_accepted}")
        print(f"Total Rejected:     {self.total_rejected}")
        print(f"Total Duplicates:   {self.total_duplicates}")
        print(f"Total New Records:  {self.total_new}")
        print("-" * 50)
        print("PER-SOURCE BREAKDOWN:")
        for name, m in self.sources.items():
            status = "FAILED" if m.error else "OK"
            print(
                f"  • {name} [{status}]: {m.fetched} fetched, {m.accepted} accepted, {m.rejected} rejected, {m.new} new ({m.duration_seconds:.2f}s)"
            )
            if m.error:
                print(f"    Error: {m.error}")
        print("-" * 50)
        if self.failed_sources:
            print(f"Failed Sources ({len(self.failed_sources)}): {', '.join(self.failed_sources)}")
        else:
            print("Failed Sources: None (100% source operational health)")
        print(f"Export Status:      {'SUCCESS' if self.export_successful else 'FAILED / PRESERVED'}")
        print("=" * 50 + "\n")


class IngestionPipeline:
    def __init__(
        self, fetchers: Optional[List[BaseFetcher]] = None, notify_telegram: bool = True, auto_export: bool = True
    ):
        self.fetchers = fetchers or [DevpostFetcher(), DevfolioFetcher(), UnstopFetcher()]
        self.notify_telegram = notify_telegram
        self.auto_export = auto_export

    def run(self) -> PipelineRunSummary:
        start_time = time.time()
        summary = PipelineRunSummary()

        all_valid_hackathons: List[Dict[str, Any]] = []

        for fetcher in self.fetchers:
            metric = SourceRunMetric(source_name=fetcher.name)
            fetcher_start = time.time()
            log(f"\n[{fetcher.name}] Starting ingestion...")

            raw_items = []
            try:
                raw_items = fetcher.fetch_safe()
                metric.fetched = len(raw_items)
            except Exception as e:
                metric.error = str(e)
                summary.failed_sources.append(fetcher.name)
                log(f"[{fetcher.name}] ERROR: {e}")

            metric.duration_seconds = round(time.time() - fetcher_start, 2)

            # Validate each item through canonical Hackathon data model
            for item in raw_items:
                try:
                    # Enrich with source if missing
                    if "source" not in item:
                        item["source"] = fetcher.name
                    validated = Hackathon(**item)
                    all_valid_hackathons.append(validated.to_dict())
                    metric.accepted += 1
                except Exception as val_err:
                    metric.rejected += 1
                    log(f"[{fetcher.name}] Rejected item '{item.get('name', 'Unknown')}': {val_err}")

            summary.sources[fetcher.name] = metric
            summary.total_fetched += metric.fetched
            summary.total_accepted += metric.accepted
            summary.total_rejected += metric.rejected

        # Ingest validated items into SQLite store with deduplication
        log(f"\n[PERSISTENCE] Ingesting {len(all_valid_hackathons)} validated records...")
        new_items = store.get_new_hackathons(all_valid_hackathons)
        summary.total_new = len(new_items)
        summary.total_duplicates = len(all_valid_hackathons) - len(new_items)

        # Notify via Telegram if requested and bot configured
        if self.notify_telegram and new_items:
            log(f"[TELEGRAM] Dispatching notifications for {len(new_items)} new hackathons...")
            for hackathon in new_items:
                try:
                    send_message(hackathon)
                except Exception as e:
                    log(f"[TELEGRAM] Notification error: {e}")

        # Export public catalog with failure-protection
        if self.auto_export:
            try:
                # If all sources failed and no hackathons accepted, exporter will preserve previous catalog
                export_public_catalog()
                summary.export_successful = True
            except Exception as exp_err:
                log(f"[EXPORTER] Catalog export failed: {exp_err}")
                summary.export_successful = False

        summary.duration_seconds = round(time.time() - start_time, 2)
        summary.print_summary()
        return summary
