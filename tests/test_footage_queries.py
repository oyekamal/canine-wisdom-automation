from harness.tools.footage import TOPIC_SEARCH_MAP, DEFAULT_QUERIES


def test_all_clusters_have_specific_queries():
    clusters = ["dog health", "dog behavior", "dog breeds", "dog training",
                "dog history", "dog science", "dog fun"]
    for cluster in clusters:
        assert cluster in TOPIC_SEARCH_MAP, f"Missing cluster: {cluster}"
        assert len(TOPIC_SEARCH_MAP[cluster]) >= 3, f"Too few queries for {cluster}"


def test_queries_are_specific_not_generic():
    for cluster, queries in TOPIC_SEARCH_MAP.items():
        for q in queries:
            assert len(q.split()) >= 2, f"Too generic query '{q}' in {cluster}"
