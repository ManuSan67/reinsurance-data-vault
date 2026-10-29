import os

from generator import write_months, write_notes


def snapshot(root):
    files = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            with open(path, encoding="utf-8") as f:
                files[os.path.relpath(path, root)] = f.read()
    return files


def rows(root, folder):
    total = 0
    for name in os.listdir(os.path.join(root, folder)):
        with open(os.path.join(root, folder, name), encoding="utf-8") as f:
            total += sum(1 for _ in f) - (1 if name.endswith(".csv") else 0)
    return total


def test_incremental_load_matches_full_load(tmp_path):
    write_months(str(tmp_path / "full"), 24)
    write_months(str(tmp_path / "incremental"), 20)
    write_months(str(tmp_path / "incremental"), 4)
    assert snapshot(tmp_path / "full") == snapshot(tmp_path / "incremental")


def test_volumes(tmp_path):
    write_months(str(tmp_path), 24)
    assert rows(tmp_path, "cedents") == 4
    assert rows(tmp_path, "treaties") == 19
    assert rows(tmp_path, "premiums") == 216
    assert rows(tmp_path, "claims/CED01") == 1179
    assert rows(tmp_path, "claims/CED02") == 1252
    assert rows(tmp_path, "claims/CED03") == 1365
    assert rows(tmp_path, "claim_notes") == 606
    assert rows(tmp_path, "claim_audit") == 100


def test_backfilled_notes_match_monthly_notes(tmp_path):
    write_months(str(tmp_path / "monthly"), 24)
    write_months(str(tmp_path / "backfill"), 24)
    for folder in ("claim_notes", "claim_audit"):
        for name in os.listdir(tmp_path / "backfill" / folder):
            os.remove(tmp_path / "backfill" / folder / name)
    write_notes(str(tmp_path / "backfill"))
    assert snapshot(tmp_path / "monthly") == snapshot(tmp_path / "backfill")