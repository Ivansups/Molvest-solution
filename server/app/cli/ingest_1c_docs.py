"""Проиндексировать уже скачанные файлы 1С через существующий RAG-пайплайн."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.documents import UnsupportedFileTypeError
from app.services.local_ingest import ingest_local_file

# Тот же id, что у консоли поддержки (frontend/src/lib/installation.ts).
DEFAULT_INSTALLATION_ID = UUID("7c77cfdc-2806-4e0f-a95f-c98d7a5b2f11")

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Точка входа: читает каталог и индексирует файлы в pgvector."""
    parser = argparse.ArgumentParser(
        description=(
            "Индексация локальных файлов 1С в базу знаний. "
            "Повтор с тем же именем пропускается (обход 409)."
        ),
    )
    parser.add_argument(
        "--dir",
        type=Path,
        required=True,
        help="каталог со скачанными файлами и опциональным manifest.tsv",
    )
    parser.add_argument(
        "--installation-id",
        type=UUID,
        default=DEFAULT_INSTALLATION_ID,
        help="installation_id консоли (по умолчанию — demo/support)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    return asyncio.run(_ingest_directory(args.dir, args.installation_id))


async def _ingest_directory(directory: Path, installation_id: UUID) -> int:
    if not directory.is_dir():
        logger.error("нет каталога: %s", directory)
        return 1

    manifest = _read_manifest(directory / "manifest.tsv")
    paths = [
        path
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != "manifest.tsv"
    ]
    if not paths:
        logger.error("в %s нет файлов", directory)
        return 1

    created = skipped = failed = 0
    async with SessionLocal() as session:
        for path in paths:
            title, source_url = manifest.get(path.name, (path.stem, ""))
            extra: dict[str, object] = {"category": "1C public docs"}
            if source_url:
                extra["source_url"] = source_url
            try:
                result = await ingest_local_file(
                    session,
                    path,
                    installation_id=installation_id,
                    title=title,
                    extra_metadata=extra,
                    app_settings=settings,
                )
            except UnsupportedFileTypeError as exc:
                logger.warning("пропуск типа: %s", exc)
                skipped += 1
                continue
            if result == "created":
                created += 1
                logger.info("проиндексирован %s", path.name)
            elif result == "skipped":
                skipped += 1
                logger.info("уже есть, пропуск %s", path.name)
            else:
                failed += 1
                logger.warning("индексация не удалась %s", path.name)

    logger.info(
        "готово created=%s skipped=%s failed=%s installation_id=%s",
        created,
        skipped,
        failed,
        installation_id,
    )
    return 1 if failed else 0


def _read_manifest(path: Path) -> dict[str, tuple[str, str]]:
    """filename → (title, source_url) из TSV, который пишет shell-скрипт."""
    if not path.is_file():
        return {}
    rows: dict[str, tuple[str, str]] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.startswith("#"):
            continue
        parts = raw.split("\t")
        if len(parts) < 2:
            continue
        file_name = parts[0].strip()
        title = parts[1].strip()
        source_url = parts[2].strip() if len(parts) > 2 else ""
        if file_name and title:
            rows[file_name] = (title, source_url)
    return rows


if __name__ == "__main__":
    sys.exit(main())
