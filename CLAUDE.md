# Chess workshop

Local chess game in Python (standard library only) with a browser front end.
Two partners extend it on separate branches and merge into `main`.

## Commands

```sh
source .venv/bin/activate      # once per terminal
python3 server.py              # open http://127.0.0.1:8000
python -m pytest               # all tests live in tests/
```

Run the full test suite before every commit and after every merge.

## Layout

- `game.py`: pure rules. A position is `[board_dict, turn]`; `board_dict` maps squares like
  `"e4"` to pieces like `"wP"`; `turn` is `"w"` or `"b"`. `move()` applies a move in place and
  returns its notation label; `undo_move()` reverses one from a history record.
- `session.py`: one game. State is `position`, `notation` (labels), `opponent`
  (`"human"` or `"computer"`), `history` (see below) and `pending`.
  `dispatch(action_dict)` handles every UI action and returns `view()`.
- `computer.py`: one-ply computer opponent, plays Black.
- `server.py`: single in-memory session, `GET /api/state`, `POST /api/action`, static files.
- `static/`: `index.html`, `app.js`, `style.css`. All rule decisions happen in Python;
  the front end only renders `view()` and sends actions.

## Shared game data (agreed by both partners)

`session.history` is a list of records, oldest first, one per move played:

```json
{"source": "e4", "target": "d5", "piece": "wP", "captured": "bP"}
```

`piece` is the piece as it stood before the move, `captured` is the piece on the target
square before the move or `null`. Records are plain JSON. Undo replays them backwards;
save/load stores and restores the list unchanged.

Save file (JSON, suffix `.save.json`, already git-ignored): keys `board`, `turn`,
`notation`, `opponent`, `history`, `pending` (bool: the last move is provisional).
Leave room for a `redo` list later.

## Turn and undo rules (agreed)

- A player's move is provisional until they press **Make turn** (`submit` action). While it
  is provisional, the opponent cannot move (`legal` returns no targets, `move` is refused)
  and the computer does not reply.
- **Undo** takes back the provisional move so the player can choose a different one. It
  only ever touches the player's own move, never the opponent's. After undoing, the player
  picks another move and submits that.
- Once a move is submitted it is final and cannot be undone.
- Undoing a provisional first move returns to the starting position.
- A move that ends the game (checkmate or stalemate) is final at once; Undo and Make turn
  are hidden once the game is over.
- Undo at the very start does nothing. Other unavailable cases raise `ValueError`.
- Against the computer the same flow applies: move, optionally undo, Make turn, then the
  computer replies. The computer's own moves are never provisional.
- Every move played is recorded in `history`; `view()` exposes `pending`, `can_undo` and
  `game_over` for the buttons and the turn text.

## Branch and file ownership while the two features are in flight

- `feature/undo`: `game.py` (`undo_move`), `session.py` (`play`, `propose`, `submit`, `undo`, `undo_one`, `can_undo`,
  `game_over`, the `"undo"`/`"submit"` branches and the pending check in `dispatch`,
  `pending`/`can_undo`/`game_over` in `view`), two buttons in `#controls`, two blocks in
  `render()`, `tests/test_undo.py`, plus two `submit` lines added to `tests/test_computer.py`.
- `feature/save-load`: `server.py`, a `restore(data)` method and `"save"`/`"load"`
  branches at the bottom of `dispatch`, a new `<div id="file-controls">` in `index.html`,
  a new block at the bottom of `app.js`, CSS rules placed after `#controls button:hover`,
  `tests/test_save_load.py`.
- Neither branch edits `__init__` beyond its own field, nor `tests/test_game.py`,
  `tests/test_computer.py`, or tooling config. Ruff, mypy and coverage go on `main`
  after both features merge.
- Merge order afterwards: `origin/feature/captured-pieces`, then `origin/feature/promotion`.
  Run tests and play the game after each merge before fixing anything.

## Testing conventions

- One test file per feature. Tests go through `Session.dispatch` for behaviour and call
  `game.py` functions directly for rules.
- When something breaks after a merge, add a test that reproduces it before fixing it.
- Remotes: `origin` is the course repo (read only). `team` is the pair's repo. Share with
  `git push -u team <branch>`, fetch with `git fetch team`.
