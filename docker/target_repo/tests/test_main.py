from src.main import query_user_records

def test_query_user_records():
    res = query_user_records(42)
    assert res["user_id"] == 42
    assert res["status"] == "active"
