import json
import random

import pytest

from computer import choose_move
from game import copy_position, move, new_position, undo_move
from session import Session


def play(session, *moves):
    """Play and submit each move in turn, as two players would."""
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})
        session.dispatch({"action": "submit"})


def propose(session, source, target):
    return session.dispatch({"action": "move", "source": source, "target": target})


def test_a_move_is_provisional_until_submitted():
    session = Session()
    view = propose(session, "e2", "e4")
    assert view["pending"] is True
    assert view["can_undo"] is True
    assert view["moves"] == ["e2-e4"]
    assert view["turn"] == "b"
    view = session.dispatch({"action": "submit"})
    assert view["pending"] is False
    assert view["can_undo"] is False
    assert view["moves"] == ["e2-e4"]


def test_opponent_cannot_move_until_the_turn_is_made():
    session = Session()
    propose(session, "e2", "e4")
    with pytest.raises(ValueError):
        propose(session, "e7", "e5")
    assert session.dispatch({"action": "legal", "source": "e7"}) == {"targets": []}
    session.dispatch({"action": "submit"})
    assert "e5" in session.dispatch({"action": "legal", "source": "e7"})["targets"]
    propose(session, "e7", "e5")
    assert session.view()["moves"] == ["e2-e4", "e7-e5"]


def test_undo_lets_the_player_choose_a_different_move():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    propose(session, "g1", "f3")
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == ["e2-e4", "e7-e5"]
    assert view["turn"] == "w"
    assert view["pending"] is False
    assert "g1" in session.position[0] and "f3" not in session.position[0]
    propose(session, "d2", "d4")
    assert session.view()["moves"] == ["e2-e4", "e7-e5", "d2-d4"]
    assert session.view()["can_undo"] is True


def test_undo_restores_a_captured_piece():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"))
    propose(session, "e4", "d5")
    assert session.view()["moves"][-1] == "e4xd5"
    session.dispatch({"action": "undo"})
    board = session.position[0]
    assert board["e4"] == "wP" and board["d5"] == "bP"
    assert len(board) == 32
    assert session.view()["moves"] == ["e2-e4", "d7-d5"]
    assert session.view()["turn"] == "w"


def test_undo_clears_check_status():
    session = Session()
    session.position = [{"e1": "wK", "a1": "wR", "e8": "bK", "h7": "bP"}, "w"]
    before = copy_position(session.position)
    propose(session, "a1", "a8")
    assert session.view()["status"] == "check"
    assert session.view()["moves"] == ["a1-a8+"]
    session.dispatch({"action": "undo"})
    assert session.view()["status"] is None
    assert session.position == before


def test_a_submitted_move_cannot_be_undone():
    session = Session()
    play(session, ("e2", "e4"))
    assert session.view()["can_undo"] is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})
    assert session.view()["moves"] == ["e2-e4"]
    # Black's provisional move can be undone, but not White's submitted one.
    propose(session, "e7", "e5")
    session.dispatch({"action": "undo"})
    assert session.view()["moves"] == ["e2-e4"]
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})


def test_undo_at_the_start_does_nothing_and_submit_needs_a_move():
    session = Session()
    assert session.view()["can_undo"] is False
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert session.position == new_position()
    with pytest.raises(ValueError):
        session.dispatch({"action": "submit"})


def test_undoing_the_first_move_returns_to_the_start():
    session = Session()
    propose(session, "e2", "e4")
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert view["turn"] == "w"
    assert session.position == new_position()
    assert session.history == []
    propose(session, "d2", "d4")
    assert session.view()["can_undo"] is True


def test_undo_works_for_both_players():
    session = Session()
    play(session, ("e2", "e4"))
    propose(session, "e7", "e5")
    assert session.view()["can_undo"] is True
    session.dispatch({"action": "undo"})
    assert session.view()["turn"] == "b"
    propose(session, "c7", "c5")
    session.dispatch({"action": "submit"})
    assert session.view()["moves"] == ["e2-e4", "c7-c5"]
    assert session.view()["turn"] == "w"


def test_a_move_that_ends_the_game_is_final_and_hides_undo():
    session = Session()
    session.position = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    view = propose(session, "a1", "a8")
    assert view["status"] == "checkmate"
    assert view["game_over"] is True
    assert view["pending"] is False
    assert view["can_undo"] is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})
    assert view["moves"] == ["a1-a8#"]


def test_computer_waits_for_the_turn_to_be_made():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    propose(session, "e2", "e4")
    assert session.computer_to_move() is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "computer-move"})
    session.dispatch({"action": "submit"})
    assert session.computer_to_move() is True
    view = session.dispatch({"action": "computer-move"})
    assert view["turn"] == "w"
    assert view["pending"] is False
    assert view["can_undo"] is False
    assert len(view["moves"]) == 2


def test_undo_against_the_computer_changes_the_move_before_it_replies():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    propose(session, "e2", "e4")
    session.dispatch({"action": "undo"})
    assert session.position == new_position()
    propose(session, "d2", "d4")
    session.dispatch({"action": "submit"})
    session.dispatch({"action": "computer-move"})
    assert session.view()["moves"][0] == "d2-d4"
    assert session.view()["turn"] == "w"


def test_new_game_clears_the_pending_move_and_history():
    session = Session()
    propose(session, "e2", "e4")
    session.dispatch({"action": "new"})
    assert session.history == []
    assert session.view()["pending"] is False
    assert session.view()["can_undo"] is False
    assert session.position == new_position()


def test_history_records_are_json_serializable():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    restored = json.loads(json.dumps(session.history))
    assert restored == session.history
    assert restored[-1] == {
        "source": "e4",
        "target": "d5",
        "piece": "wP",
        "captured": "bP",
    }
    assert restored[0]["captured"] is None


def test_undo_move_reverses_any_sequence_exactly():
    rng = random.Random(3)
    position = new_position()
    snapshots, records = [], []
    for _ in range(30):
        chosen = choose_move(position, rng)
        if chosen is None:
            break
        source, target = chosen
        snapshots.append(copy_position(position))
        records.append(
            {
                "source": source,
                "target": target,
                "piece": position[0][source],
                "captured": position[0].get(target),
            }
        )
        move(position, source, target)
    while records:
        undo_move(position, records.pop())
        assert position == snapshots.pop()
    assert position == new_position()


def test_unknown_actions_are_still_rejected():
    session = Session()
    with pytest.raises(ValueError):
        session.dispatch({"action": "redo"})
