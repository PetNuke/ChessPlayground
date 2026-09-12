"""
Text-only chess client for ChessEngine.

Play from a terminal, a pipe, or --moves so the engine can be tested
without pygame.

Moves: SAN (Nf3, O-O, exd6, e8=Q) or UCI/coordinate (e2e4, e7e8q).
Commands: help, board, moves, undo, log, fen, resign, quit.
"""

from __future__ import annotations

import argparse
import sys

import ChessEngine

FILES = ChessEngine.Move.filesToCols
RANKS = ChessEngine.Move.ranksToRows
PROMOTION_LETTERS = "QRBN"

PIECE_CHARS = {
    "wK": "K", "wQ": "Q", "wR": "R", "wB": "B", "wN": "N", "wp": "P",
    "bK": "k", "bQ": "q", "bR": "r", "bB": "b", "bN": "n", "bp": "p",
    ChessEngine.BLANK_SPACE: ".",
}

HELP_TEXT = """\
Commands:
  help, h, ?     show this help
  board, b       print the board
  moves, m       list legal moves (coordinate notation)
  undo, u        take back the last move
  log, history   show moves played
  fen            print a FEN of the current position
  resign         end the game for the side to move
  quit, exit, q  leave

Moves:
  SAN:  e4, Nf3, O-O, O-O-O, exd6, e8=Q, Nbd7
  UCI:  e2e4, e1g1, e7e8q
  Several tokens on one line are played in order.
"""


class MoveError(ValueError):
    """Raised when a typed move cannot be played."""


def in_check(gs):
    king = "wK" if gs.whiteToMove else "bK"
    for row in range(8):
        for col in range(8):
            if gs.board[row][col] == king:
                return gs.squareUnderAttack(row, col)
    return False


def game_status(gs):
    legal = gs.getValidMoves()
    checked = in_check(gs)
    if len(legal) == 0:
        if checked:
            winner = "Black" if gs.whiteToMove else "White"
            return "checkmate", "%s is checkmated. %s wins." % (
                "White" if gs.whiteToMove else "Black", winner)
        return "stalemate", "Stalemate. Draw."
    if checked:
        return "check", "%s is in check." % ("White" if gs.whiteToMove else "Black")
    return "ok", "%s to move." % ("White" if gs.whiteToMove else "Black")


def render_board(gs):
    lines = ["  a b c d e f g h"]
    for row in range(8):
        rank = ChessEngine.Move.rowsToRanks[row]
        cells = [PIECE_CHARS.get(gs.board[row][col], "?") for col in range(8)]
        lines.append("%s %s %s" % (rank, " ".join(cells), rank))
    lines.append("  a b c d e f g h")
    return "\n".join(lines)


def to_fen(gs):
    ranks = []
    for row in range(8):
        empty = 0
        fen_row = []
        for col in range(8):
            piece = gs.board[row][col]
            if piece == ChessEngine.BLANK_SPACE:
                empty += 1
                continue
            if empty:
                fen_row.append(str(empty))
                empty = 0
            fen_row.append(PIECE_CHARS[piece])
        if empty:
            fen_row.append(str(empty))
        ranks.append("".join(fen_row))

    castle = ""
    if gs.whiteCanCastleKing:
        castle += "K"
    if gs.whiteCanCastleQueen:
        castle += "Q"
    if gs.blackCanCastleKing:
        castle += "k"
    if gs.blackCanCastleQueen:
        castle += "q"
    if not castle:
        castle = "-"

    ep = "-"
    if gs.moveLog:
        last = gs.moveLog[-1]
        if last.pieceMoved[1] == "p" and abs(last.startRow - last.endRow) == 2:
            mid_row = (last.startRow + last.endRow) // 2
            ep = last.getRankFile(mid_row, last.endCol)

    turn = "w" if gs.whiteToMove else "b"
    return "%s %s %s %s 0 %s" % (
        "/".join(ranks), turn, castle, ep, len(gs.moveLog) // 2 + 1)


def strip_check_marks(san):
    san = san.replace("e.p.", "").replace("e.p", "")
    return san.replace("+", "").replace("#", "").replace("!", "").replace("?", "")


def move_matches_san(move, san):
    san = strip_check_marks(san)
    if san in ("O-O", "0-0"):
        return move.castle and move.endCol == 6
    if san in ("O-O-O", "0-0-0"):
        return move.castle and move.endCol == 2

    promotion = None
    if "=" in san:
        san, promotion = san.split("=", 1)
        promotion = promotion[0].upper()
    elif len(san) >= 3 and san[-1] in PROMOTION_LETTERS and san[-2] in RANKS:
        promotion = san[-1]
        san = san[:-1]

    san_no_x = san.replace("x", "")
    if len(san_no_x) < 2:
        return False
    dest = san_no_x[-2:]
    dest_file, dest_rank = dest[0], dest[1]
    if dest_file not in FILES or dest_rank not in RANKS:
        return False
    if move.endCol != FILES[dest_file] or move.endRow != RANKS[dest_rank]:
        return False

    if promotion:
        return bool(move.pawnPromotion and move.promotionPiece
                    and move.promotionPiece[1] == promotion)

    prefix = san_no_x[:-2]
    if prefix and prefix[0] in "KQRBN":
        piece = prefix[0]
        disambig = prefix[1:]
    else:
        piece = "p"
        disambig = prefix

    if move.pieceMoved[1] != piece:
        return False

    if len(disambig) == 1:
        ch = disambig[0]
        if ch in FILES:
            return move.startCol == FILES[ch]
        if ch in RANKS:
            return move.startRow == RANKS[ch]
        return False
    if len(disambig) == 2:
        return (disambig[0] in FILES and disambig[1] in RANKS
                and move.startCol == FILES[disambig[0]]
                and move.startRow == RANKS[disambig[1]])
    return True


def parse_uci(token):
    """Return (start, end, promo) or None. promo is 'Q'/'R'/'B'/'N' or None."""
    raw = token.strip().replace("-", "")
    if len(raw) not in (4, 5):
        return None
    start, end = raw[:2].lower(), raw[2:4].lower()
    if start[0] not in FILES or start[1] not in RANKS:
        return None
    if end[0] not in FILES or end[1] not in RANKS:
        return None
    promo = None
    if len(raw) == 5:
        promo = raw[5 - 1].upper()
        if promo not in PROMOTION_LETTERS:
            return None
    start_sq = (RANKS[start[1]], FILES[start[0]])
    end_sq = (RANKS[end[1]], FILES[end[0]])
    return start_sq, end_sq, promo


def find_legal_move(gs, token, legal=None):
    if legal is None:
        legal = gs.getValidMoves()
    token = token.strip()
    if not token:
        raise MoveError("empty move")

    uci = parse_uci(token)
    if uci is not None:
        start, end, promo = uci
        matches = [m for m in legal
                   if m.startRow == start[0] and m.startCol == start[1]
                   and m.endRow == end[0] and m.endCol == end[1]]
        if promo:
            matches = [m for m in matches
                       if m.pawnPromotion and m.promotionPiece
                       and m.promotionPiece[1] == promo]
        elif any(m.pawnPromotion for m in matches):
            matches = [m for m in matches
                       if m.pawnPromotion and m.promotionPiece
                       and m.promotionPiece[1] == "Q"]
        if len(matches) == 1:
            return matches[0]
        if len(matches) == 0:
            raise MoveError("illegal move: %s" % token)
        raise MoveError("ambiguous move: %s" % token)

    matches = [m for m in legal if move_matches_san(m, token)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) == 0:
        raise MoveError("illegal move: %s" % token)
    raise MoveError(
        "ambiguous move: %s (try coordinates: %s)"
        % (token, ", ".join(m.getChessNotation() for m in matches))
    )


def format_move_log(gs):
    if not gs.moveLog:
        return "(no moves yet)"
    parts = []
    for i, move in enumerate(gs.moveLog):
        note = move.getChessNotation()
        extras = []
        if move.castle:
            extras.append("O-O-O" if move.endCol == 2 else "O-O")
        if move.enpassant:
            extras.append("e.p.")
        if move.pawnPromotion:
            extras.append("=%s" % move.promotionPiece[1])
        if extras:
            note += " (%s)" % ", ".join(extras)
        if i % 2 == 0:
            parts.append("%d. %s" % (i // 2 + 1, note))
        else:
            parts.append(note)
    return " ".join(parts)


class HeadlessGame:
    def __init__(self):
        self.gs = ChessEngine.GameState()
        self.over_message = None
        self.resigned = False

    def legal_moves(self):
        return self.gs.getValidMoves()

    def refresh_status(self):
        if self.resigned:
            return
        kind, message = game_status(self.gs)
        if kind in ("checkmate", "stalemate"):
            self.over_message = message

    def play_token(self, token):
        if self.over_message:
            raise MoveError("game is over (%s). undo or quit." % self.over_message)
        move = find_legal_move(self.gs, token)
        self.gs.makeMove(move)
        self.refresh_status()
        return move

    def play_tokens(self, tokens):
        played = []
        for token in tokens:
            played.append(self.play_token(token))
        return played

    def undo(self):
        if not self.gs.moveLog:
            raise MoveError("no moves to undo")
        self.gs.undoMove()
        self.over_message = None
        self.resigned = False
        self.refresh_status()

    def resign(self):
        side = "White" if self.gs.whiteToMove else "Black"
        winner = "Black" if self.gs.whiteToMove else "White"
        self.resigned = True
        self.over_message = "%s resigns. %s wins." % (side, winner)
        return self.over_message


COMMANDS = {
    "help", "h", "?",
    "board", "b",
    "moves", "m",
    "undo", "u",
    "log", "history",
    "fen",
    "resign",
    "quit", "exit", "q",
}


def handle_command(game, command, out):
    """Handle a non-move command. Return False to quit."""
    if command in ("help", "h", "?"):
        out(HELP_TEXT)
    elif command in ("board", "b"):
        out(render_board(game.gs))
        kind, message = game_status(game.gs) if not game.resigned else ("over", game.over_message)
        out(game.over_message if game.over_message and game.resigned else message)
    elif command in ("moves", "m"):
        legal = game.legal_moves()
        if not legal:
            out("(no legal moves)")
        else:
            out(" ".join(sorted(m.getChessNotation() for m in legal)))
    elif command in ("undo", "u"):
        game.undo()
        out("Undid last move.")
        out(render_board(game.gs))
        _, message = game_status(game.gs)
        out(message)
    elif command in ("log", "history"):
        out(format_move_log(game.gs))
    elif command == "fen":
        out(to_fen(game.gs))
    elif command == "resign":
        out(game.resign())
    elif command in ("quit", "exit", "q"):
        return False
    return True


def handle_line(game, line, out):
    """
    Process one input line. Returns False if the session should end.
    """
    line = line.strip()
    if not line:
        return True
    if line.startswith("#"):
        return True

    tokens = line.split()
    if len(tokens) == 1 and tokens[0].lower() in COMMANDS:
        try:
            return handle_command(game, tokens[0].lower(), out)
        except MoveError as err:
            out("Error: %s" % err)
            return True

    i = 0
    while i < len(tokens):
        token = tokens[i]
        lowered = token.lower()
        if lowered in COMMANDS:
            try:
                if not handle_command(game, lowered, out):
                    return False
            except MoveError as err:
                out("Error: %s" % err)
                return True
            i += 1
            continue
        try:
            move = game.play_token(token)
        except MoveError as err:
            out("Error: %s" % err)
            out("Stopped before: %s" % " ".join(tokens[i:]))
            return True
        extras = []
        if move.castle:
            extras.append("castle")
        if move.enpassant:
            extras.append("en passant")
        if move.pawnPromotion:
            extras.append("promotion to %s" % move.promotionPiece[1])
        extra = " [%s]" % ", ".join(extras) if extras else ""
        out("Played %s%s" % (move.getChessNotation(), extra))
        i += 1

    out(render_board(game.gs))
    if game.over_message:
        out(game.over_message)
    else:
        _, message = game_status(game.gs)
        out(message)
    return True


def run_session(lines, out, show_opening_board=True):
    game = HeadlessGame()
    if show_opening_board:
        out(render_board(game.gs))
        out("White to move. Type help for commands.")
    for line in lines:
        if not handle_line(game, line, out):
            break
    return game


def prompt_lines(stdin, stdout):
    while True:
        try:
            stdout.write("> ")
            stdout.flush()
            line = stdin.readline()
        except EOFError:
            break
        if line == "":
            break
        yield line


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Play ChessEngine from the terminal (no pygame).")
    parser.add_argument(
        "--moves", "-m",
        help="Play these moves (quoted, space-separated), then print the board.")
    parser.add_argument(
        "--file", "-f",
        help="Read commands/moves from a text file.")
    parser.add_argument(
        "--interactive", "-i", action="store_true",
        help="After --moves/--file, keep a prompt open.")
    parser.add_argument(
        "--quiet", action="store_true",
        help="Do not print the starting board.")
    args = parser.parse_args(argv)

    out = lambda text: print(text, file=sys.stdout)

    game = HeadlessGame()
    if not args.quiet:
        out(render_board(game.gs))
        out("White to move. Type help for commands.")

    def consume(source):
        for line in source:
            if not handle_line(game, line, out):
                return False
        return True

    keep_going = True
    if args.moves:
        keep_going = consume([args.moves])
    if keep_going and args.file:
        with open(args.file, encoding="utf-8") as handle:
            keep_going = consume(handle)

    scripted = bool(args.moves or args.file)
    if scripted and not args.interactive:
        return 0 if keep_going else 0

    if keep_going:
        for line in prompt_lines(sys.stdin, sys.stdout):
            if not handle_line(game, line, out):
                break
    out("Goodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
