from app.db import SessionLocal
from app.services.run_ingest import run_all
from app.models import IngestRun
from datetime import datetime

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
