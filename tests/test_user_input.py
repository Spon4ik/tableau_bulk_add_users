from helpers.user_input import normalize_users


def test_normalize_users_preserves_order_and_deduplicates_case_insensitively():
    assert normalize_users([" Alice ", "bob", "ALICE", "", " Bob "]) == ["Alice", "bob"]
