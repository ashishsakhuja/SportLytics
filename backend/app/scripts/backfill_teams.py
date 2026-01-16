from __future__ import annotations

from typing import Any, Dict, List, Optional

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ContentItem
from app.services.enrich import extract_teams


def _entities_get_teams(entities: Any) -> List[str]:
    if not isinstance(entities, dict):
        return []
    t = entities.get("teams", [])
    if isinstance(t, list):
        return [str(x) for x in t if x]
    return []


def _entities_set_teams(entities: Any, teams: List[str]) -> Dict[str, Any]:
    base: Dict[str, Any] = entities if isinstance(entities, dict) else {}
    base["teams"] = teams
    base.setdefault("players", [])
    base.setdefault("leagues", [])
    return base


def _needs_backfill(item: ContentItem) -> bool:
    col_teams = list(getattr(item, "teams", None) or [])
    ent_teams = _entities_get_teams(getattr(item, "entities", None))
    return (len(col_teams) == 0) or (len(ent_teams) == 0)


def backfill(db: Session, batch_size: int = 500, max_rows: Optional[int] = None) -> None:
    scanned = 0
    updated = 0
    last_id = 0

    while True:
        # Pull rows in ascending id order and advance with a cursor (last_id).
        # We filter at DB level to avoid scanning rows that are already filled.
        rows = (
            db.query(ContentItem)
            .filter(ContentItem.id > last_id)
            .filter(
                sa.or_(
                    # teams array missing or empty
                    sa.func.coalesce(sa.func.cardinality(ContentItem.teams), 0) == 0,
                    # entities missing or entities.teams missing/empty (cheap JSON existence checks)
                    ContentItem.entities.is_(None),
                    sa.func.coalesce(sa.func.jsonb_array_length(ContentItem.entities["teams"]), 0) == 0,
                )
            )
            .order_by(ContentItem.id.asc())
            .limit(batch_size)
            .all()
        )

        if not rows:
            break

        batch_updated = 0

        for item in rows:
            last_id = item.id
            scanned += 1
            if max_rows is not None and scanned > max_rows:
                db.commit()
                print(f"[BACKFILL] reached max_rows={max_rows}")
                print(f"[BACKFILL] scanned={scanned} updated={updated}")
                return

            if not _needs_backfill(item):
                continue

            title = item.title or ""
            text = (item.snippet or "") or (getattr(item, "summary", "") or "")

            # This calls YOUR updated extract_teams(), which uses TEAM_ALIASES.
            new_teams = extract_teams(title, text)

            if not new_teams:
                continue

            col_teams = list(getattr(item, "teams", None) or [])
            ent_teams = _entities_get_teams(getattr(item, "entities", None))

            # Only fill empty fields (don’t overwrite existing)
            changed = False

            if len(col_teams) == 0:
                item.teams = new_teams
                changed = True

            if len(ent_teams) == 0:
                item.entities = _entities_set_teams(getattr(item, "entities", None), new_teams)
                changed = True

            if changed:
                batch_updated += 1
                updated += 1

        db.commit()
        print(f"[BACKFILL] progress: scanned={scanned} updated={updated} last_id={last_id} batch_updated={batch_updated}")

        # If a whole batch produced zero updates, it usually means remaining rows
        # don’t contain recognizable aliases. We can stop early.
        if batch_updated == 0:
            print("[BACKFILL] No updates in this batch — stopping early (remaining rows not taggable by extractor).")
            break

    print(f"[BACKFILL] DONE scanned={scanned} updated={updated}")


def main():
    db = SessionLocal()
    try:
        backfill(db, batch_size=500, max_rows=None)
    finally:
        db.close()


if __name__ == "__main__":
    main()
