"""Application actions and information shown beside the board."""

from computer import choose_move
from game import (
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
        else:
            raise ValueError("Unknown action")
        return self.view()
