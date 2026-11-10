import json
import threading
from http.client import HTTPConnection

import pytest

from game import new_position
from server import make_server
from session import Session


def play(session, *moves):
    """Play and submit each move in turn, as two players would."""
    for source, target in moves:
        session.dispatch({"action": "move", "source": source, "target": target})
        session.dispatch({"action": "submit"})


def saved(session):
    """The save file's contents, after a real JSON round trip."""
    return json.loads(json.dumps(session.dispatch({"action": "save"})["game"]))


def test_save_captures_board_turn_notation_and_opponent():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    game = saved(session)
    assert game["board"]["e4"] == "wP" and "e2" not in game["board"]
    assert game["turn"] == "b"
    assert game["notation"] == ["e2-e4"]
    assert game["opponent"] == "computer"
    assert set(game) >= {"board", "turn", "notation", "opponent", "history", "pending"}


def test_load_resumes_the_game_in_a_fresh_session():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    game = saved(session)

    fresh = Session()
    view = fresh.dispatch({"action": "load", "game": game})
    assert fresh.position == session.position
    assert view["moves"] == ["e2-e4", "d7-d5", "e4xd5"]
    assert view["turn"] == "b"
    assert view["opponent"] == "human"
    # Play continues from the loaded position.
    play(fresh, ("d8", "d5"))
    assert fresh.view()["moves"][-1] == "d8xd5"


def test_load_preserves_the_opponent_mode():
    session = Session()
    session.dispatch({"action": "new", "opponent": "computer"})
    play(session, ("e2", "e4"))
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved(session)})
    assert fresh.view()["opponent"] == "computer"
    assert fresh.computer_to_move()
    fresh.dispatch({"action": "computer-move"})
    assert fresh.view()["turn"] == "w"


def test_load_preserves_undo_history_and_pending_flag():
    session = Session()
    play(session, ("e2", "e4"), ("d7", "d5"), ("e4", "d5"))
    game = saved(session)
    # Whatever the undo feature records travels with the save file unchanged.
    game["history"] = [
        {"source": "e2", "target": "e4", "piece": "wP", "captured": None}
    ]
    game["pending"] = True
    fresh = Session()
    fresh.dispatch({"action": "load", "game": game})
    assert fresh.history == game["history"]
    assert fresh.pending is True
    assert saved(fresh)["history"] == game["history"]


def test_save_and_load_a_finished_game():
    session = Session()
    session.position = [
        {"g1": "wK", "a1": "wR", "g8": "bK", "f7": "bP", "g7": "bP", "h7": "bP"},
        "w",
    ]
    # A mating move is final at once, so there is nothing to submit.
    session.dispatch({"action": "move", "source": "a1", "target": "a8"})
    fresh = Session()
    view = fresh.dispatch({"action": "load", "game": saved(session)})
    assert view["status"] == "checkmate"
    assert view["winner"] == "White"


def test_load_replaces_the_current_game_entirely():
    session = Session()
    play(session, ("e2", "e4"), ("e7", "e5"), ("g1", "f3"))
    game = saved(session)
    other = Session()
    other.dispatch({"action": "new", "opponent": "computer"})
    play(other, ("d2", "d4"))
    other.dispatch({"action": "load", "game": game})
    assert other.view()["moves"] == ["e2-e4", "e7-e5", "g1-f3"]
    assert other.view()["opponent"] == "human"
    assert other.position == session.position


def test_new_game_after_load_starts_clean():
    session = Session()
    play(session, ("e2", "e4"))
    fresh = Session()
    fresh.dispatch({"action": "load", "game": saved(session)})
    fresh.dispatch({"action": "new"})
    assert fresh.position == new_position()
    assert fresh.view()["moves"] == []


@pytest.mark.parametrize(
    "corrupt",
    [
        None,
        "not a game",
        {},
        {"board": {}, "turn": "w"},
        {"board": {"z9": "wK"}, "turn": "w"},
        {"board": {"e1": "wX"}, "turn": "w"},
        {"board": {"e1": "wK", "e8": "bK"}, "turn": "x"},
        {"board": {"e1": "wK", "e8": "bK"}, "turn": "w", "notation": "e2-e4"},
        {"board": {"e1": "wK", "e8": "bK"}, "turn": "w", "history": [1, 2]},
        {"board": {"e1": "wK", "e8": "bK"}, "turn": "w", "opponent": "robot"},
    ],
)
def test_corrupt_save_files_are_rejected_and_leave_the_game_alone(corrupt):
    session = Session()
    play(session, ("e2", "e4"))
    before = session.view()
    with pytest.raises(ValueError):
        session.dispatch({"action": "load", "game": corrupt})
    assert session.view() == before


def test_server_serves_the_save_file_as_a_download():
    server = make_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request(
            "POST",
            "/api/action",
            body=json.dumps({"action": "move", "source": "e2", "target": "e4"}),
            headers={"Content-Type": "application/json"},
        )
        assert connection.getresponse().status == 200
        connection.request("GET", "/api/save")
        response = connection.getresponse()
        assert response.status == 200
        assert "attachment" in response.getheader("Content-Disposition")
        assert response.getheader("Content-Disposition").endswith('.save.json"')
        game = json.loads(response.read())
        assert game["notation"] == ["e2-e4"]
        # The same file loads back over the action endpoint.
        connection.request(
            "POST",
            "/api/action",
            body=json.dumps({"action": "load", "game": game}),
            headers={"Content-Type": "application/json"},
        )
        loaded = json.loads(connection.getresponse().read())
        assert loaded["moves"] == ["e2-e4"]
    finally:
        server.shutdown()
        server.server_close()
