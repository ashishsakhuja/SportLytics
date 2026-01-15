from datetime import datetime

from app.db import SessionLocal
from app.models import IngestRun, ContentItem
from app.services.run_ingest import run_all


def main():
    db = SessionLocal()
    run = IngestRun(status="running", started_at=datetime.utcnow(), inserted_count=0)

    try:
        db.add(run)
        db.commit()
        db.refresh(run)

        inserted = run_all(db)

        run.status = "success"
        run.inserted_count = int(inserted)
        run.finished_at = datetime.utcnow()
        run.error = None
        db.commit()

        print(f"Inserted {inserted} items.")

        # Optional: print a small sanity sample so you can confirm enrichment fields are populated
        sample = (
            db.query(ContentItem)
            .order_by(ContentItem.published_at.desc())
            .limit(5)
            .all()
        )

        if sample:
            print("\n[ENRICH SAMPLE] latest 5 content_items:")
            for x in sample:
                print(
                    f"- sport={x.sport} source={x.source} "
                    f"dup={getattr(x, 'is_duplicate', None)} "
                    f"rank={getattr(x, 'rank_score', None)} "
                    f"urg={getattr(x, 'urgency', None)} "
                    f"topics={getattr(x, 'topics', None)} "
                    f"teams={(getattr(x, 'entities', None) or {}).get('teams', []) if getattr(x, 'entities', None) else []} "
                    f"title={x.title[:90]!r}"
                )

    except Exception as e:
        # best effort to record failure
        try:
            run.status = "failed"
            run.finished_at = datetime.utcnow()
            run.error = str(e)[:2000]
            db.commit()
        except Exception:
            pass
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()
