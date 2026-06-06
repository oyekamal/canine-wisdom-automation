import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[3]))

from channels.dailyygstories.harness.asset_matcher import extract_setting_keywords, map_keywords_to_pexels_query


def test_extract_setting_keywords_from_script_data():
    script_data = {"setting_keywords": ["dark forest", "abandoned house", "hospital"]}
    keywords = extract_setting_keywords(script_data)
    assert keywords == ["dark forest", "abandoned house", "hospital"]


def test_extract_setting_keywords_fallback_when_missing():
    script_data = {"script": "I was walking through dark woods at night alone..."}
    keywords = extract_setting_keywords(script_data)
    assert isinstance(keywords, list)
    assert len(keywords) > 0


def test_map_keywords_to_pexels_query_returns_string():
    keywords = ["dark forest", "night"]
    query = map_keywords_to_pexels_query(keywords, story_type="paranormal")
    assert isinstance(query, str)
    assert len(query) > 3


def test_map_keywords_empty_falls_back_to_story_type():
    query = map_keywords_to_pexels_query([], story_type="true_crime")
    assert "crime" in query.lower() or "dark" in query.lower() or "night" in query.lower()
