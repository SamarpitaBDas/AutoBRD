"""
Management command: load_enron_csv

Parses the Enron email dataset CSV and loads it into the Django DB as
DataSource + ExtractedRequirement records so BRDGenerator can query them
normally via the ORM.

Usage:
    python manage.py load_enron_csv \
        --csv /path/to/emails.csv \
        --project "My Project" \
        --product "energy trading platform" \   # optional topic filter
        --limit 500                              # optional row cap
"""

import csv
import re
import sys
from email import message_from_string
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User

# Guard against running outside Django
try:
    from api.models import Project, DataSource, ExtractedRequirement
except ImportError:
    raise SystemExit("Run this command via: python manage.py load_enron_csv ...")

from ml_models.requirement_extractor import RequirementExtractor


class Command(BaseCommand):
    help = "Load Enron email CSV dataset into the BRD database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--csv",
            required=True,
            help="Path to the Enron emails CSV file (columns: file, message)",
        )
        parser.add_argument(
            "--project",
            default="Enron Dataset Project",
            help="Name of the Django Project to attach data to",
        )
        parser.add_argument(
            "--product",
            default=None,
            help=(
                "Optional: only import emails relevant to this product/topic "
                "(e.g. 'energy trading platform'). Uses ML relevance filtering."
            ),
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Maximum number of CSV rows to process (default: all)",
        )
        parser.add_argument(
            "--min-relevance",
            type=float,
            default=0.35,
            help="Minimum relevance score to mark a DataSource as relevant (default: 0.35)",
        )

    def handle(self, *args, **options):
        csv_path = options["csv"]
        project_name = options["project"]
        product_topic = options["product"]
        limit = options["limit"]
        min_relevance = options["min_relevance"]

        self.stdout.write(self.style.MIGRATE_HEADING(f"\n📂  Loading CSV: {csv_path}"))
        self.stdout.write(f"📋  Project     : {project_name}")
        if product_topic:
            self.stdout.write(f"🎯  Topic filter: {product_topic}")

        # ── 1. Get or create Project ──────────────────────────────────────────
        user, _ = User.objects.get_or_create(username="hackathon_loader")
        project, created = Project.objects.get_or_create(
            name=project_name,
            defaults={
                "description": (
                    f"Auto-loaded from Enron email dataset. "
                    f"Topic: {product_topic or 'general'}"
                ),
                "user": user,
            },
        )
        action = "Created" if created else "Found existing"
        self.stdout.write(f"✅  {action} project: {project.name} (id={project.id})\n")

        # ── 2. Initialise ML extractor ────────────────────────────────────────
        self.stdout.write("🤖  Loading ML models (this may take 30-60 s the first run)…")
        extractor = RequirementExtractor()
        self.stdout.write("✅  ML models ready\n")

        # ── 3. Stream CSV ─────────────────────────────────────────────────────
        total_rows = imported = skipped_noise = skipped_topic = req_count = 0

        try:
            csvfile = open(csv_path, newline="", encoding="utf-8", errors="replace")
        except FileNotFoundError:
            self.stderr.write(self.style.ERROR(f"File not found: {csv_path}"))
            sys.exit(1)

        reader = csv.DictReader(csvfile)

        for row in reader:
            if limit and total_rows >= limit:
                break
            total_rows += 1

            file_id = row.get("file", "").strip()
            raw_message = row.get("message", "").strip()

            if not raw_message:
                skipped_noise += 1
                continue

            # ── 3a. Parse email headers ───────────────────────────────────────
            parsed = _parse_email_headers(raw_message)
            body = parsed["body"]

            if len(body.split()) < 5:
                skipped_noise += 1
                continue

            # ── 3b. Product/topic relevance filter ────────────────────────────
            if product_topic:
                relevant, score = extractor.filter_for_product(body, product_topic)
            else:
                relevant, score = extractor.filter_noise(body)

            if not relevant:
                skipped_topic += 1
                continue

            # ── 3c. Save DataSource ───────────────────────────────────────────
            ds = DataSource.objects.create(
                project=project,
                source_type="email",
                source_identifier=file_id or f"enron_row_{total_rows}",
                raw_content=raw_message,
                processed_content=body,
                is_relevant=(score >= min_relevance),
                relevance_score=score,
            )
            ds.set_metadata(
                {
                    "from": parsed.get("from", ""),
                    "to": parsed.get("to", ""),
                    "subject": parsed.get("subject", ""),
                    "date": parsed.get("date", ""),
                    "dataset": "enron",
                }
            )
            ds.save()
            imported += 1

            # ── 3d. Extract requirements ──────────────────────────────────────
            if ds.is_relevant:
                requirements = extractor.extract_requirements(body, ds)
                for req_data in requirements:
                    ExtractedRequirement.objects.create(
                        project=project,
                        data_source=ds,
                        requirement_type=req_data["requirement_type"],
                        title=req_data["title"],
                        description=req_data["description"],
                        priority=req_data["priority"],
                        stakeholder=req_data.get("stakeholder", ""),
                        confidence_score=req_data["confidence_score"],
                    )
                    req_count += 1

            # ── Progress tick ─────────────────────────────────────────────────
            if total_rows % 50 == 0:
                self.stdout.write(
                    f"  … processed {total_rows} rows | "
                    f"imported {imported} | reqs {req_count}"
                )

        csvfile.close()

        # ── 4. Summary ────────────────────────────────────────────────────────
        self.stdout.write("\n" + "─" * 50)
        self.stdout.write(self.style.SUCCESS("✅  Import complete"))
        self.stdout.write(f"   Rows processed   : {total_rows}")
        self.stdout.write(f"   Emails imported  : {imported}")
        self.stdout.write(f"   Skipped (noise)  : {skipped_noise}")
        self.stdout.write(f"   Skipped (off-topic): {skipped_topic}")
        self.stdout.write(f"   Requirements found: {req_count}")
        self.stdout.write(
            f"\n   Project id {project.id} is ready — "
            "run generate_brd against it now."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_email_headers(raw: str) -> dict:
    """
    Use Python's stdlib email parser to cleanly split headers from body.
    Falls back gracefully if the message is malformed.
    """
    try:
        msg = message_from_string(raw)
        body = msg.get_payload()
        if isinstance(body, list):          # multipart — join text parts
            body = "\n".join(
                p.get_payload(decode=True).decode("utf-8", errors="replace")
                for p in body
                if p.get_content_type() == "text/plain"
            )
        elif isinstance(body, bytes):
            body = body.decode("utf-8", errors="replace")
        return {
            "from": msg.get("From", ""),
            "to": msg.get("To", ""),
            "subject": msg.get("Subject", ""),
            "date": msg.get("Date", ""),
            "body": (body or "").strip(),
        }
    except Exception:
        # If parsing fails just return the raw text as the body
        return {"from": "", "to": "", "subject": "", "date": "", "body": raw}
