"""Application actions and information shown beside the board."""

from computer import choose_move
from game import (
    FILES,
    legal_moves,
    move,
    new_position,
    status,
    winner,
)


# Legal from the standard starting position under this game's rules.
# Next move: b7-a8, capturing a rook and reaching the last rank.
PROMOTION_SETUP = [
    ("a2", "a4"), ("h7", "h5"),
    ("a4", "a5"), ("h5", "h4"),
    ("a5", "a6"), ("h4", "h3"),
    ("a6", "b7"), ("h3", "g2"),
]


def as_list(value):
    """A list as given, or [None] so that any element check fails for non-lists."""
    return value if isinstance(value, list) else [None]


class Session:
    def __init__(self, opponent="human"):
        if opponent not in ("human", "computer"):
            raise ValueError("Unknown opponent")
        self.position = new_position()
        self.notation = []
        self.opponent = opponent

    def play(self, source, target):
        label = move(self.position, source, target)
        self.notation.append(label)
        self.after_move()

    def after_move(self):
        pass

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {}

    def snapshot(self):
        """Everything needed to resume this game elsewhere, as plain JSON data.
        The undo history and pending flag are included when the session has them."""
        return {
            "board": dict(self.position[0]),
            "turn": self.position[1],
            "notation": list(self.notation),
            "opponent": self.opponent,
            "history": list(getattr(self, "history", [])),
            "pending": bool(getattr(self, "pending", False)),
        }

    def restore(self, data):
        """Replace this game with a saved one. Rejects anything malformed."""
        if not isinstance(data, dict):
            raise ValueError("Expected a saved game")
        board, turn = data.get("board"), data.get("turn")
        notation, history = data.get("notation", []), data.get("history", [])
        if not isinstance(board, dict) or not board:
            raise ValueError("Saved game has no board")
        for square, piece in board.items():
            if not (isinstance(square, str) and len(square) == 2
                    and square[0] in FILES and square[1] in "12345678"):
                raise ValueError(f"Saved game has a bad square: {square!r}")
            if not (isinstance(piece, str) and len(piece) == 2
                    and piece[0] in "wb" and piece[1] in "KQRBNP"):
                raise ValueError(f"Saved game has a bad piece: {piece!r}")
        if turn not in ("w", "b"):
            raise ValueError("Saved game has a bad turn")
        if not all(isinstance(m, str) for m in as_list(notation)):
            raise ValueError("Saved game has bad notation")
        if not all(isinstance(r, dict) for r in as_list(history)):
            raise ValueError("Saved game has bad history")
        self.__init__(data.get("opponent", "human"))
        self.position = [dict(board), turn]
        self.notation = notation
        self.history = history
        self.pending = bool(data.get("pending", False))

    def dispatch(self, action):
        command = action.get("action")
        if command == "move":
            if self.computer_to_move():
                raise ValueError("Wait for the computer's move")
            self.play(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        elif command == "save":
            return {"game": self.snapshot()}
        elif command == "load":
            self.restore(action.get("game"))
        else:
            raise ValueError("Unknown action")
        return self.view()
