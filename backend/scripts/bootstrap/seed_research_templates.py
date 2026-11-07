"""Add concrete research templates; default is a read-only preview.

From backend/: PYTHONPATH=src:. .venv/bin/python scripts/bootstrap/seed_research_templates.py
Take a database backup before adding --apply. Existing templates are never updated.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import sqlalchemy as sa

CATALOG_PATH = Path(__file__).resolve().parents[2] / 'data/templates/research-presets-v1.json'
REPORT_TYPES = {'research-demand', 'technology-route', 'project-demand'}


def load_presets(path: Path = CATALOG_PATH) -> list[dict]:
    catalog = json.loads(path.read_text(encoding='utf-8'))
    if catalog.get('version') != 1:
        raise ValueError('Unsupported research template catalog version')
    rows = catalog['templates']
    seen = set()
    for row in rows:
        key = (row['report_type'], row['name'])
        if row['purpose'] != 'research' or row['report_type'] not in REPORT_TYPES or key in seen:
            raise ValueError('Invalid or duplicated research template binding')
        seen.add(key)
        if not row['name'].strip() or not row['prompt'].strip() or not row['description'].strip():
            raise ValueError('Template content is required')
        sections = row['sections']
        if len(sections) < 4 or len({section['title'] for section in sections}) != len(sections):
            raise ValueError('A template requires distinct substantive sections')
        for section in sections:
            if (
                not section['description'].strip()
                or type(section['words']) is not int
                or not 1 <= section['words'] <= 8000
            ):
                raise ValueError('Invalid section guidance or word target')
        if row.get('model_id') is not None or row.get('image_model_id') is not None or row['image_config']['enabled']:
            raise ValueError('Presets must not choose models or enable image generation')
    counts = Counter(row['report_type'] for row in rows)
    if set(counts) != REPORT_TYPES or min(counts.values()) < 2:
        raise ValueError('Each report type needs multiple concrete templates')
    return rows


def install_presets(connection, table, presets: list[dict], *, apply: bool = False) -> dict:
    """One transaction, append only, stable matching by explicit type and name."""
    if apply and connection.dialect.name == 'postgresql':
        connection.execute(sa.text("SELECT pg_advisory_xact_lock(hashtext('pipesight-research-presets-v1'))"))
    existing = {}
    for row in connection.execute(
        sa.select(table.c.id, table.c.name, table.c.report_type).where(table.c.purpose == 'research')
    ):
        existing.setdefault((row.report_type, row.name), []).append(row.id)
    pending, skipped = [], []
    for preset in presets:
        matches = existing.get((preset['report_type'], preset['name']), [])
        if len(matches) > 1:
            raise ValueError('Ambiguous template identity; nothing was changed')
        if matches:
            skipped.append({'id': str(matches[0]), 'name': preset['name']})
        else:
            pending.append(preset)
    created = []
    if apply:
        for preset in pending:
            ident = connection.scalar(sa.insert(table).values(**preset).returning(table.c.id))
            created.append({'id': str(ident), 'name': preset['name'], 'reportType': preset['report_type']})
    return {
        'applied': apply,
        'pending': [{'name': row['name'], 'reportType': row['report_type']} for row in pending],
        'created': created,
        'preserved': skipped,
    }


def main(apply: bool = False) -> None:
    from app.infrastructure.models.registry import register_sqlalchemy_models
    from app.intelligence.models.configuration import PipelineTemplateVersion
    from config.database import create_sync_db_engine

    presets = load_presets()
    register_sqlalchemy_models()
    engine = create_sync_db_engine(echo=False)
    try:
        with engine.begin() as connection:
            result = install_presets(connection, PipelineTemplateVersion.__table__, presets, apply=apply)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', help='Append templates after taking a database backup')
    args = parser.parse_args()
    main(args.apply)
