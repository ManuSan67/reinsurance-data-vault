import os

from generator import write_months


def snapshot(root):
    files = {}
    for folder, _, names in os.walk(root):
        for name in names:
            path = os.path.join(folder, name)
            with open(path) as f:
                files[os.path.relpath(path, root)] = f.read()
    return files


def rows(root, folder):
    total = 0
    for name in os.listdir(os.path.join(root, folder)):
        with open(os.path.join(root, folder, name)) as f:
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
