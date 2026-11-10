# Lab 5 review: extended chess game and its tests

Agent review written by Claude (Claude Code) for the pair's submission.
Repository: `limr7890-source/aicode-lab05-chess`, branch `main` at commit `6e62ff5`.
Date: 2026-11-10.

## 1. What was built

Two features were added on separate branches from the starter commit and merged into `main`.

### Undo with a confirm-your-turn flow (`feature/undo`)

The pair agreed on this behaviour and recorded it in `CLAUDE.md`:

- A player's move is **provisional** until they press **Make turn**. While it is provisional
  the opponent cannot move or select pieces, and the computer does not reply.
- **Undo** takes the provisional move back so the player can choose a different one. It only
  ever touches the player's own move, never the opponent's.
- A submitted move is final and cannot be undone. Undoing a provisional first move returns to
  the starting position. Undo at the very start does nothing.
- A move that ends the game is final at once; Undo and Make turn are hidden when the game is
  over.
- Against the computer the same flow applies: move, optionally undo, Make turn, then the
  computer replies. The computer's own moves are never provisional.

Implementation: every move appends a record `{source, target, piece, captured}` to
`session.history`; `game.undo_move` reverses one record in place, restoring the moved piece and
any captured piece and flipping the turn. `Session.propose` plays a provisional move,
`Session.submit` makes it final, `Session.undo` reverts it. The view exposes `pending`,
`can_undo` and `game_over` for the two buttons and the turn text.

### Save and load (`feature/save-load`)

- **Save game** downloads `chess.save.json` from a new `GET /api/save` route.
- **Load game** uploads a file; the browser sends it as a `load` action and the server replaces
  the current game. A fresh server instance can therefore resume a saved game.
- The file holds `board`, `turn`, `notation`, `opponent`, `history` and `pending`, which is
  everything undo needs after a load.
- `Session.restore` validates the file (squares, pieces, turn, notation, history, opponent) and
  rejects malformed input with a `ValueError`, leaving the current game untouched.

## 2. How the work was organised

- `CLAUDE.md` was written on `main` before the features were built. It fixes the shared
  data model (the history record, the save-file keys), the undo rules, and which files and
  functions each branch may touch. This kept the two branches apart: the merge into `main`
  produced no conflicts.
- Each branch carries its own test file: `tests/test_undo.py` and `tests/test_save_load.py`.
- The undo rules changed four times during the session as the pair refined what undo should
  mean (take back two half-moves; take back one; repeated undo; finally the confirm-your-turn
  flow). Each change was made with its tests before moving on, and `CLAUDE.md` was updated
  each time so the save/load side always knew what to store.

## 3. Tests

68 tests pass on `main` (`python -m pytest`). By file:

| File | Tests | What they establish |
| --- | --- | --- |
| `tests/test_game.py` | 13 | Starter rules: movement, check, checkmate, stalemate, notation. |
| `tests/test_computer.py` | 8 | Starter computer opponent. Two tests gained a `submit` step. |
| `tests/test_undo.py` | 16 | Provisional moves, opponent blocked, undo for both players, captures and check restored, submitted moves final, game-ending move final, computer waits for Make turn, new game clears state, history is JSON-safe, randomised 30-move undo round trip. |
| `tests/test_save_load.py` | 9 (one with 10 parametrised corrupt files) | Round trip into a fresh session, play continues after load, opponent mode kept, finished game, load replaces the current game, corrupt files rejected without side effects, a real HTTP test of the download header and the load endpoint. |
| `tests/test_integration.py` | 7 | The two features together (next section). |

### Interactions found when merging

After the merge, four save/load tests and one more failed. All five played consecutive moves
without a Make turn between them, which the merged rules block ("Undo or submit your move
first"), and one tried to submit a mating move, which is final at once. The game code was
correct; the tests written on the save/load branch assumed the starter's turn model. They were
fixed to submit each move, and seven integration tests were added for behaviour neither branch
could test alone:

1. Save during a pending move, load into a fresh session, undo restores the captured piece,
   play continues.
2. Save during a pending move, load, the opponent stays blocked until Make turn.
3. Loaded submitted moves cannot be undone; history arrives intact.
4. Loading over a pending move discards it.
5. Undo before save leaves no trace of the undone move in the file.
6. A pending move against the computer survives save and load; the computer waits for Make turn.
7. New game after load clears both features' state.

A live check through the HTTP server confirmed the first scenario end to end.

## 4. Checking tools

Run on `main` with ruff 0.17.4, mypy and coverage installed into `.venv`. No tool
configuration was added to the repository.

| Tool | Result | Notes |
| --- | --- | --- |
| `python -m pytest` | 68 passed | |
| `coverage` | 92% overall; `game.py` 100%, `session.py` 100%, `computer.py` 97%, `server.py` 62% | Uncovered: the `__main__` block, static file routes, and request-size and JSON error paths in `server.py`; one line in `computer.py`. |
| `ruff check` | 3 findings | `session.py` import block unsorted (pre-existing on the starter), two `TRY004` suggestions to raise `TypeError` instead of `ValueError` (one pre-existing in `server.py`, one in the new `restore`). |
| `ruff format --check` | 6 files would be reformatted | All in starter code style. New code was range-formatted; whole files were deliberately left alone on the feature branches to avoid merge conflicts. |
| `mypy --strict` | 84 errors in 4 files | The starter is untyped (55 errors before this work). New functions are annotated; remaining new findings come from calling untyped starter functions. |

### Coverage gaps and behaviour the tests do not check

- The browser side (`static/app.js`) is untested. The button enabling, the turn text while a
  move is pending, and the file picker are only checked by hand.
- `server.py` is covered only by one HTTP test. The 404 route, oversized requests and
  malformed JSON are not exercised.
- Save files are validated structurally, not for legality: a file with two white kings or a
  king in check for the wrong side loads without complaint.
- Undo and save/load have not yet been tested together with captured-pieces display or
  promotion, because those branches are not merged yet (next section).

## 5. Remaining lab steps

Not done in this session, in the order the lab asks:

1. Merge `origin/feature/captured-pieces`, run the tests, play. Expected interactions: the
   display must drop a piece when its capture is undone, and must be restored from a save file.
2. Merge `origin/feature/promotion`. Expected interactions: undo of a promotion must bring the
   pawn back (the history record stores the piece before the move, so this should work without
   changes), and a promoted piece must survive save and load.
3. Format and type the starter code on `main` now that both branches are merged, so the
   tools above pass cleanly.
4. Redo, using `history` plus a redo list in the save file, as `CLAUDE.md` already reserves.

## 6. Reviewer's assessment

- **Correctness**: the merged game behaves as the pair specified. Rules live in Python, the
  front end only renders the view.
- **Design**: storing the moved piece in each history record makes undo independent of later
  features such as promotion. Writing `history` and `pending` generically in `snapshot` and
  `restore` let save/load be developed on a branch that did not have those fields.
- **Risk**: the confirm-your-turn flow changed the meaning of the `move` action for every
  existing test and for the supplied branches. Expect the captured-pieces and promotion test
  files to need the same `submit` step when they are merged.
- **Process**: the no-conflict merge and the quick diagnosis of the five post-merge failures
  both trace back to agreeing the data model and file ownership in `CLAUDE.md` first.
