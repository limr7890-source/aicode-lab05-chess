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
        # Set by undo, cleared by the next move: one undo per turn.
        self.undone_this_turn = False

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
        self.undone_this_turn = False
        self.after_move()

    def after_move(self):
        pass

    def game_over(self) -> bool:
        return status(self.position) in ("checkmate", "stalemate")

    def can_undo(self) -> bool:
        """The side to move may take back its own last move, once per turn, while
        the game is on. That needs the opponent's reply and the player's move."""
        return (
            len(self.history) >= 2
            and not self.undone_this_turn
            and not self.game_over()
        )

    def undo(self) -> None:
        """Reverse the player's last move together with the reply that followed it.
        Taking back the first move of the game restarts the game. Undo does
        nothing at the start and is refused when it is not available."""
        if not self.history:
            return
        if self.game_over():
            raise ValueError("The game is over")
        if self.undone_this_turn:
            raise ValueError("Undo is available once per turn")
        if len(self.history) < 2:
            raise ValueError("You can only undo your own move")
        for _ in range(2):
            undo_move(self.position, self.history.pop())
            self.notation.pop()
        if self.history:
            self.undone_this_turn = True
        else:
            self.__init__(self.opponent)

    def view(self):
        return {
            "board": self.position[0],
            "turn": self.position[1],
            "moves": self.notation,
            "opponent": self.opponent,
            "status": status(self.position),
            "winner": winner(self.position),
            "can_undo": self.can_undo(),
            "game_over": self.game_over(),
            **self.sidebar(),
        }

    def computer_to_move(self):
        return (self.opponent == "computer" and self.position[1] == "b"
                and status(self.position) not in ("checkmate", "stalemate"))

    def sidebar(self):
        return {}

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
        elif command == "undo":
            self.undo()
        elif command == "new":
            self.__init__(action.get("opponent", "human"))
        elif command == "promotion-setup":
            self.__init__()
            for source, target in PROMOTION_SETUP:
                self.play(source, target)
        else:
            raise ValueError("Unknown action")
        return self.view()
