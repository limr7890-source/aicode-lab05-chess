import json
import random

import pytest

from computer import choose_move
from game import copy_position, move, new_position, undo_move
from session import Session


def play(session, *moves):
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})


def test_undo_takes_back_the_players_move_and_the_reply():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"))
    after_two = None
    session2 = Session()
    play(session2, ("e2", "e4"), ("e7", "e5"))
    after_two = copy_position(session2.position)
    view = session.dispatch({"action": "undo"})
    assert session.position == after_two
    assert view["turn"] == "w"
    assert view["moves"] == ["e2-e4", "e7-e5"]


def test_undo_restores_a_captured_piece():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"), ("d8", "d5"))
    assert session.view()["moves"] == ["e2-e4", "d7-d5", "e4xd5", "d8xd5"]
    session.dispatch({"action": "undo"})
    board = session.position[0]
    assert board["e4"] == "wP" and board["d5"] == "bP" and board["d8"] == "bQ"
    assert len(board) == 32
    assert session.view()["moves"] == ["e2-e4", "d7-d5"]
    assert session.view()["turn"] == "w"


def test_undo_clears_check_status():
    session = Session()
    start = {"e1": "wK", "a1": "wR", "e8": "bK", "h7": "bP"}
    session.position = [dict(start), "w"]
    play(session, ("a1", "a8"), ("e8", "e7"))
    assert session.view()["moves"] == ["a1-a8+", "e8-e7"]
    play(session, ("a8", "a7"), ("e7", "e6"))
    session.dispatch({"action": "undo"})
    assert session.view()["moves"] == ["a1-a8+", "e8-e7"]
    assert session.position[0]["a8"] == "wR"
    assert session.view()["status"] is None


def test_undo_at_the_start_does_nothing():
    session = Session()
    assert session.view()["can_undo"] is False
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert session.position == new_position()


def test_only_the_side_to_move_can_undo_its_own_move():
    session = Session()
    play(session, ("e2", "e4"))
    # Black is to move, but the only move is White's.
    assert session.view()["can_undo"] is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})
    assert session.view()["moves"] == ["e2-e4"]


def test_undoing_the_first_move_restarts_the_game():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert view["turn"] == "w"
    assert session.position == new_position()
    assert session.history == []
    assert session.undone_this_turn is False
    assert view["can_undo"] is False


def test_undo_is_available_once_per_turn():
    session = Session()
    play(
        session,
        ("e2", "e4"),
        ("e7", "e5"),
        ("g1", "f3"),
        ("b8", "c6"),
        ("f1", "c4"),
        ("f8", "c5"),
    )
    assert session.view()["can_undo"] is True
    session.dispatch({"action": "undo"})
    assert len(session.view()["moves"]) == 4
    assert session.view()["can_undo"] is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})
    assert len(session.view()["moves"]) == 4
    # A move ends the turn; undo opens up again for the next player.
    play(session, ("d2", "d4"))
    assert session.view()["can_undo"] is True


def test_undo_disappears_when_the_game_ends():
    session = Session()
    session.position = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    play(session, ("a1", "a2"), ("g8", "h8"), ("a2", "a8"))
    view = session.view()
    assert view["status"] == "checkmate"
    assert view["game_over"] is True
    assert view["can_undo"] is False
    with pytest.raises(ValueError):
        session.dispatch({"action": "undo"})
    assert view["moves"] == ["a1-a2", "g8-h8", "a2-a8#"]


def test_undo_then_a_different_move_is_legal():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"), ("b8", "c6"))
    session.dispatch({"action": "undo"})
    play(session, ("d2", "d4"))
    assert session.view()["moves"] == ["e2-e4", "e7-e5", "d2-d4"]
    assert "g1" in session.position[0] and "f3" not in session.position[0]


def test_undo_against_the_computer_reverses_its_reply_too():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    assert session.view()["turn"] == "w"
    assert session.view()["can_undo"] is True
    view = session.dispatch({"action": "undo"})
    assert view["moves"] == []
    assert view["turn"] == "w"
    assert view["opponent"] == "computer"
    assert session.position == new_position()
    assert session.computer_to_move() is False


def test_undo_against_the_computer_leaves_earlier_pairs_intact():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    session.dispatch({"action": "computer-move"})
    after_first_pair = copy_position(session.position)
    play(session, ("d2", "d4"))
    session.dispatch({"action": "computer-move"})
    assert len(session.view()["moves"]) == 4
    session.dispatch({"action": "undo"})
    assert len(session.view()["moves"]) == 2
    assert session.position == after_first_pair
    assert session.view()["can_undo"] is False


def test_new_game_clears_the_undo_history():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"))
    session.dispatch({"action": "new"})
    assert session.history == []
    assert session.view()["can_undo"] is False
    session.dispatch({"action": "undo"})
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
