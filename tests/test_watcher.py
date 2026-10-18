import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from watcher import find_matching_slots


def test_finds_relevant_level_3_after_6pm():
    text = "Adult Tennis Level 3 course available at 18:30 on Tuesday."
    matches = find_matching_slots(text, ["adult", "level 3"], "18:00", "20:00")
    assert matches


def test_ignores_wrong_level_or_time():
    text = "Adult Tennis Level 2 course available at 21:00."
    matches = find_matching_slots(text, ["adult", "level 3"], "18:00", "20:00")
    assert not matches
