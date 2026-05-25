from harness.tools.footage import TOPIC_SEARCH_MAP


def test_queries_match_todd_examples():
    """Queries must be phrase-level specific per client request."""
    all_queries = [q for queries in TOPIC_SEARCH_MAP.values() for q in queries]
    assert any("panting" in q for q in all_queries), "Missing anxiety+panting query"
    assert any("trick" in q or "learning" in q for q in all_queries), "Missing puppy learning tricks"
    assert any("veterinarian" in q or "vet" in q.lower() for q in all_queries), "Missing vet query"


def test_all_queries_at_least_two_words():
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert len(q.split()) >= 2, f"Too short: '{q}' in {cluster}"


def test_no_generic_single_word_queries():
    bad = {"dog", "puppy", "vet", "training", "fun"}
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert q.lower() not in bad, f"Generic query '{q}' in {cluster}"
