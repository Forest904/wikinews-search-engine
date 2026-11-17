"""Demo fixtures must be useful and must not duplicate or overwrite work."""
import importlib.util
from pathlib import Path

from wikinews_ir.annotation import connect, create_user, tasks
from wikinews_ir.annotation_export import export_snapshot
from wikinews_ir.annotation_workflow import review_tasks

spec = importlib.util.spec_from_file_location("local_mock", Path(__file__).resolve().parents[2] / "scripts/local_mock.py")
mock = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mock)


def test_mock_population_is_repeatable_and_covers_workflows(tmp_path):
    path = tmp_path / "annotation.sqlite3"
    with connect(path) as db:
        create_user(db, "luca", "test-only-password", coordinator=True)
    packet = mock.populate(path)
    with connect(path) as db:
        before = db.execute("SELECT count(*) FROM judgments").fetchone()[0]
        personal = tasks(db, "luca")
        assert len(personal) == 4
        assert {t["own_judgment"]["status"] if t["own_judgment"] else "unstarted" for t in personal} == {"judged", "deferred", "needs_review", "unstarted"}
        assert len(review_tasks(db, "luca")) == 1
        assert db.execute("SELECT count(*) FROM blocks WHERE active=0").fetchone()[0] == 1
        assert export_snapshot(db, "luca", packet, "development")["judgments"]
    assert mock.populate(path) == packet
    with connect(path) as db:
        assert db.execute("SELECT count(*) FROM judgments").fetchone()[0] == before
        assert db.execute("SELECT count(*) FROM blocks").fetchone()[0] == 3
