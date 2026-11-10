"""Save/load and undo working together."""

import json

from game import new_position
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})
        session.dispatch({"action": "submit"})


def saved(session):
    return json.loads(json.dumps(session.dispatch({"action": "save"})["game"]))


def test_save_during_a_pending_move_then_load_and_undo():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"))
    session.dispatch({"action": "move", "source": "e4", "target": "d5"})
    game = saved(session)
    assert game["pending"] is True
    assert game["history"][-1] == {
        "source": "e4",
        "target": "d5",
        "piece": "wP",
        "captured": "bP",
    }

    fresh = Session()
    view = fresh.dispatch({"action": "load", "game": game})
    assert view["pending"] is True and view["can_undo"] is True
    # The loaded player can still change their mind, and the capture is restored.
    view = fresh.dispatch({"action": "undo"})
    assert view["moves"] == ["e2-e4", "d7-d5"]
    assert fresh.position[0]["e4"] == "wP" and fresh.position[0]["d5"] == "bP"
    assert len(fresh.position[0]) == 32
    play(fresh, ("d2", "d4"))
    assert fresh.view()["moves"] == ["e2-e4", "d7-d5", "d2-d4"]


def test_save_during_a_pending_move_then_load_and_submit():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved(session)})
    with_pending = fresh.dispatch({"action": "legal", "source": "g1"})
    assert with_pending == {"targets": []}
    fresh.dispatch({"action": "submit"})
    assert fresh.view()["pending"] is False
    assert "f3" in fresh.dispatch({"action": "legal", "source": "g1"})["targets"]


def test_loaded_submitted_moves_cannot_be_undone():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    fresh = Session()
    view = fresh.dispatch({"action": "load", "game": saved(session)})
    assert view["pending"] is False and view["can_undo"] is False
    assert fresh.history == session.history
    assert fresh.view()["moves"] == ["e2-e4", "e7-e5"]


def test_loading_during_a_pending_move_discards_it():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    game = saved(session)
    other = Session()
    other.dispatch({"action": "move", "source": "d2", "target": "d4"})
    assert other.view()["pending"] is True
    other.dispatch({"action": "load", "game": game})
    assert other.view()["pending"] is False
    assert other.view()["moves"] == ["e2-e4", "e7-e5"]
    assert other.history == session.history


def test_undo_then_save_does_not_keep_the_undone_move():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    session.dispatch({"action": "undo"})
    game = saved(session)
    assert game["notation"] == ["e2-e4"]
    assert [r["source"] for r in game["history"]] == ["e2"]
    assert game["pending"] is False
    assert game["turn"] == "b"


def test_pending_move_against_the_computer_survives_save_and_load():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    session.dispatch({"action": "move", "source": "e2", "target": "e4"})
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved(session)})
    assert fresh.view()["opponent"] == "computer"
    assert fresh.computer_to_move() is False
    fresh.dispatch({"action": "submit"})
    assert fresh.computer_to_move() is True
    fresh.dispatch({"action": "computer-move"})
    assert fresh.view()["turn"] == "w"
    assert len(fresh.view()["moves"]) == 2


def test_new_game_after_load_clears_history_and_pending():
    session = Session()
    play(session, ("e2", "e4"))
    session.dispatch({"action": "move", "source": "e7", "target": "e5"})
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved(session)})
    fresh.dispatch({"action": "new"})
    assert fresh.position == new_position()
    assert fresh.history == [] and fresh.pending is False
    assert fresh.view()["can_undo"] is False
