"""Application actions and information shown beside the board."""

from computer import choose_move
from game import (
    FILES,
    legal_moves,
    move,
    new_position,
    status,
    undo_move,
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
        # One record per move played, oldest first; what undo needs to reverse it.
        self.history = []
        # The last move is provisional: its player may still undo it or submit it.
        self.pending = False

    def play(self, source, target):
        board = self.position[0]
        record = {
            "source": source,
            "target": target,
            "piece": board.get(source),
            "captured": board.get(target),
        }
        label = move(self.position, source, target)
        self.history.append(record)
        self.notation.append(label)
        self.after_move()

    def propose(self, source, target):
        """A player's move. It stays provisional until submitted, so the player
        can undo it and choose another. A move that ends the game is final."""
        if self.pending:
            raise ValueError("Undo or submit your move first")
        self.play(source, target)
        self.pending = not self.game_over()

    def submit(self) -> None:
        """Make the turn: the provisional move becomes final and the opponent moves."""
        if not self.pending:
            raise ValueError("There is no move to submit")
        self.pending = False

    def after_move(self):
        pass

    def game_over(self) -> bool:
        return status(self.position) in ("checkmate", "stalemate")

    def can_undo(self) -> bool:
        """Only the move you just made, before you submit it, can be undone."""
        return self.pending and not self.game_over()

    def undo(self) -> None:
        """Take back the provisional move so its player can choose another. Undo
        does nothing at the start and is refused once a move has been submitted."""
        if not self.history:
            return
        if self.game_over():
            raise ValueError("The game is over")
        if not self.pending:
            raise ValueError("Only the move you just made can be undone")
        self.undo_one()
        self.pending = False

    def undo_one(self) -> None:
        undo_move(self.position, self.history.pop())
        self.notation.pop()

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            "pending": self.pending,
            "can_undo": self.can_undo(),
            "game_over": self.game_over(),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and not self.pending
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
            self.propose(action.get("source"), action.get("target"))
        elif command == "computer-move":
            if not self.computer_to_move():
                raise ValueError("It is not the computer's turn")
            self.play(*choose_move(self.position))
        elif command == "legal":
            if self.pending:
                return {"targets": []}
            return {"targets": legal_moves(self.position, action.get("source"))}
        elif command == "undo":
            self.undo()
        elif command == "submit":
            self.submit()
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
