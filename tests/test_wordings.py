from wordings import all_clauses


def test_clauses():
    clauses = all_clauses()
    assert len(clauses) == 109
    assert len({(c["treaty_number"], c["clause_no"]) for c in clauses}) == 109
    endorsements = [c for c in clauses if c["title"] == "Endoso 1"]
    assert [c["treaty_number"] for c in endorsements] == ["T-CED01-MOTOR-2024"]
    assert "del 50% al 35%" in endorsements[0]["chunk"]