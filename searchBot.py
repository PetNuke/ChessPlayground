"""
Framework for search bots: SearchBot(depth, eval_fn).

`depth` is plies of minimax (alpha-beta). `eval_fn(gs)` is a greedy-style
leaf evaluator: higher is better for the side to move.

Mate in one is always chosen when it exists, before any eval.

    bot = SearchBot(depth=8, eval_fn=greedy_eval)
    bot = SearchBot(depth=8, eval_fn=rules_eval, name="mine")
"""

from __future__ import annotations

import random
import sys
import time

import ChessEngine
import headlessPlay

PIECE_VALUES = {"p": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
MATE_SCORE = 100000
INF = 10 ** 9
SEARCH8_DEPTH = 8

BLANK = ChessEngine.BLANK_SPACE


class _NodeLimit(Exception):
    pass


def greedy_eval(gs):
    """Material score for the side to move (captures raise it)."""
    return _signed_score(gs, _material_white(gs.board))


piece_value_eval = greedy_eval


def random_eval(gs):
    """Deterministic pseudo-random score so search stays stable per position."""
    total = 746829 + int(gs.whiteToMove)
    for row, rank in enumerate(gs.board):
        for col, piece in enumerate(rank):
            if piece == BLANK:
                continue
            total = (total * 167 + row * 17 + col * 3 + ord(piece[0]) * 13
                     + ord(piece[1]) * 29) & 0x7FFFFFFF
    return (total % 201) - 100


# Piece-square tables are in engine coords for White (row 0 = rank 8).
# Black uses the vertically flipped table.

_PST_PAWN = (
    ( 0,  0,  0,  0,  0,  0,  0,  0),
    (50, 50, 50, 50, 50, 50, 50, 50),
    (10, 10, 20, 30, 30, 20, 10, 10),
    ( 5,  5, 10, 25, 25, 10,  5,  5),
    ( 0,  0,  0, 20, 20,  0,  0,  0),
    ( 5, -5,-10,  0,  0,-10, -5,  5),
    ( 5, 10, 10,-20,-20, 10, 10,  5),
    ( 0,  0,  0,  0,  0,  0,  0,  0),
)
_PST_KNIGHT = (
    (-50,-40,-30,-30,-30,-30,-40,-50),
    (-40,-20,  0,  0,  0,  0,-20,-40),
    (-30,  0, 10, 15, 15, 10,  0,-30),
    (-30,  5, 15, 20, 20, 15,  5,-30),
    (-30,  0, 15, 20, 20, 15,  0,-30),
    (-30,  5, 10, 15, 15, 10,  5,-30),
    (-40,-20,  0,  5,  5,  0,-20,-40),
    (-50,-40,-30,-30,-30,-30,-40,-50),
)
_PST_BISHOP = (
    (-20,-10,-10,-10,-10,-10,-10,-20),
    (-10,  0,  0,  0,  0,  0,  0,-10),
    (-10,  0,  5, 10, 10,  5,  0,-10),
    (-10,  5,  5, 10, 10,  5,  5,-10),
    (-10,  0, 10, 10, 10, 10,  0,-10),
    (-10, 10, 10, 10, 10, 10, 10,-10),
    (-10,  5,  0,  0,  0,  0,  5,-10),
    (-20,-10,-10,-10,-10,-10,-10,-20),
)
_PST_ROOK = (
    ( 0,  0,  0,  0,  0,  0,  0,  0),
    ( 5, 10, 10, 10, 10, 10, 10,  5),
    (-5,  0,  0,  0,  0,  0,  0, -5),
    (-5,  0,  0,  0,  0,  0,  0, -5),
    (-5,  0,  0,  0,  0,  0,  0, -5),
    (-5,  0,  0,  0,  0,  0,  0, -5),
    (-5,  0,  0,  0,  0,  0,  0, -5),
    ( 0,  0,  0,  5,  5,  0,  0,  0),
)
_PST_QUEEN = (
    (-20,-10,-10, -5, -5,-10,-10,-20),
    (-10,  0,  0,  0,  0,  0,  0,-10),
    (-10,  0,  5,  5,  5,  5,  0,-10),
    ( -5,  0,  5,  5,  5,  5,  0, -5),
    (  0,  0,  5,  5,  5,  5,  0, -5),
    (-10,  5,  5,  5,  5,  5,  0,-10),
    (-10,  0,  5,  0,  0,  0,  0,-10),
    (-20,-10,-10, -5, -5,-10,-10,-20),
)
_PST_KING_MID = (
    (-30,-40,-40,-50,-50,-40,-40,-30),
    (-30,-40,-40,-50,-50,-40,-40,-30),
    (-30,-40,-40,-50,-50,-40,-40,-30),
    (-30,-40,-40,-50,-50,-40,-40,-30),
    (-20,-30,-30,-40,-40,-30,-30,-20),
    (-10,-20,-20,-20,-20,-20,-20,-10),
    ( 20, 20,  0,  0,  0,  0, 20, 20),
    ( 20, 30, 10,  0,  0, 10, 30, 20),
)
_PST_KING_END = (
    (-50,-40,-30,-20,-20,-30,-40,-50),
    (-30,-20,-10,  0,  0,-10,-20,-30),
    (-30,-10, 20, 30, 30, 20,-10,-30),
    (-30,-10, 30, 40, 40, 30,-10,-30),
    (-30,-10, 30, 40, 40, 30,-10,-30),
    (-30,-10, 20, 30, 30, 20,-10,-30),
    (-30,-30,  0,  0,  0,  0,-30,-30),
    (-50,-30,-30,-30,-30,-30,-30,-50),
)

_PST = {"p": _PST_PAWN, "N": _PST_KNIGHT, "B": _PST_BISHOP, "R": _PST_ROOK, "Q": _PST_QUEEN}


def rules_eval(gs):
    """Many static rules on top of piece values: structure, king, development."""
    board = gs.board
    material = 0
    pst = 0
    bishops = {"w": 0, "b": 0}
    minors_home = {"w": 0, "b": 0}
    pawns_on_file = {"w": [0] * 8, "b": [0] * 8}
    pawn_rows = {"w": [[] for _ in range(8)], "b": [[] for _ in range(8)]}
    kings = {"w": None, "b": None}
    queens = {"w": 0, "b": 0}
    rooks = []
    non_pawn = 0

    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == BLANK:
                continue
            color, kind = piece[0], piece[1]
            sign = 1 if color == "w" else -1
            if kind == "K":
                kings[color] = (row, col)
                continue
            material += sign * PIECE_VALUES.get(kind, 0)
            if kind != "p":
                non_pawn += PIECE_VALUES.get(kind, 0)
            table = _PST.get(kind)
            if table is not None:
                pst_row = row if color == "w" else 7 - row
                pst += sign * table[pst_row][col]
            if kind == "B":
                bishops[color] += 1
            elif kind == "Q":
                queens[color] += 1
            elif kind == "R":
                rooks.append((color, row, col))
            elif kind == "p":
                pawns_on_file[color][col] += 1
                pawn_rows[color][col].append(row)
            if kind in ("N", "B"):
                home = 7 if color == "w" else 0
                if row == home:
                    minors_home[color] += 1

    endgame = non_pawn <= 1600
    king_table = _PST_KING_END if endgame else _PST_KING_MID
    for color, sign in (("w", 1), ("b", -1)):
        if kings[color] is None:
            continue
        row, col = kings[color]
        pst_row = row if color == "w" else 7 - row
        pst += sign * king_table[pst_row][col]

    structure = 0
    structure += _pawn_structure(board, pawns_on_file, pawn_rows, "w")
    structure -= _pawn_structure(board, pawns_on_file, pawn_rows, "b")

    pair = 0
    if bishops["w"] >= 2:
        pair += 40
    if bishops["b"] >= 2:
        pair -= 40

    develop = (minors_home["b"] - minors_home["w"]) * 12

    castle = 0
    if gs.whiteCanCastleKing:
        castle += 20
    if gs.whiteCanCastleQueen:
        castle += 12
    if gs.blackCanCastleKing:
        castle -= 20
    if gs.blackCanCastleQueen:
        castle -= 12

    center = 0
    for row, col, bonus in ((4, 3, 16), (4, 4, 18), (3, 3, 16), (3, 4, 18),
                            (5, 3, 8), (5, 4, 8), (2, 3, 8), (2, 4, 8)):
        piece = board[row][col]
        if piece == BLANK:
            continue
        sign = 1 if piece[0] == "w" else -1
        if piece[1] == "p":
            center += sign * bonus
        elif piece[1] in ("N", "B"):
            center += sign * (bonus // 2)

    files_with_pawns = [pawns_on_file["w"][c] + pawns_on_file["b"][c] for c in range(8)]
    rook_score = 0
    for color, row, col in rooks:
        sign = 1 if color == "w" else -1
        own = pawns_on_file[color][col]
        opp = pawns_on_file["b" if color == "w" else "w"][col]
        if own == 0 and opp == 0:
            rook_score += sign * 22
        elif own == 0:
            rook_score += sign * 10
        seventh = 1 if color == "w" else 6
        if row == seventh:
            rook_score += sign * 24

    shield = 0
    shield += _king_shield(board, kings["w"], "w")
    shield -= _king_shield(board, kings["b"], "b")

    early_queen = 0
    if not endgame:
        if queens["w"] and _queen_off_home(board, "w"):
            early_queen -= 8 * minors_home["w"]
        if queens["b"] and _queen_off_home(board, "b"):
            early_queen += 8 * minors_home["b"]

    total = (material + pst + structure + pair + develop + castle
             + center + rook_score + shield + early_queen)
    return total if gs.whiteToMove else -total


def _signed_score(gs, white_score):
    return white_score if gs.whiteToMove else -white_score


def _material_white(board):
    score = 0
    for row in board:
        for piece in row:
            if piece == BLANK or piece[1] == "K":
                continue
            value = PIECE_VALUES.get(piece[1], 0)
            score += value if piece[0] == "w" else -value
    return score


def _pawn_structure(board, pawns_on_file, pawn_rows, color):
    score = 0
    own_files = pawns_on_file[color]
    for col in range(8):
        count = own_files[col]
        if count >= 2:
            score -= 14 * (count - 1)
        if count and not _adjacent_own_pawn(own_files, col):
            score -= 12
        for row in pawn_rows[color][col]:
            if _is_passed(board, row, col, color):
                advance = (6 - row) if color == "w" else (row - 1)
                score += 18 + 12 * max(0, advance)
    return score


def _adjacent_own_pawn(own_files, col):
    if col > 0 and own_files[col - 1]:
        return True
    if col < 7 and own_files[col + 1]:
        return True
    return False


def _is_passed(board, row, col, color):
    enemy = "bp" if color == "w" else "wp"
    if color == "w":
        ahead = range(row - 1, -1, -1)
    else:
        ahead = range(row + 1, 8)
    for r in ahead:
        for c in (col - 1, col, col + 1):
            if 0 <= c < 8 and board[r][c] == enemy:
                return False
    return True


def _king_shield(board, king, color):
    if king is None:
        return 0
    row, col = king
    home = 7 if color == "w" else 0
    if abs(row - home) > 1:
        return 0
    pawn = color + "p"
    step = -1 if color == "w" else 1
    score = 0
    for dc in (-1, 0, 1):
        c = col + dc
        r = row + step
        if 0 <= c < 8 and 0 <= r < 8 and board[r][c] == pawn:
            score += 10
        elif 0 <= c < 8 and 0 <= r + step < 8 and board[r + step][c] == pawn:
            score += 4
        else:
            score -= 8
    return score


def _queen_off_home(board, color):
    home = 7 if color == "w" else 0
    queen = color + "Q"
    for col in range(8):
        if board[home][col] == queen:
            return False
    for row in board:
        if queen in row:
            return True
    return False


def _insufficient_material(board):
    extras = []
    for row in board:
        for piece in row:
            if piece == BLANK or piece[1] == "K":
                continue
            if piece[1] not in ("N", "B"):
                return False
            extras.append(piece)
    return len(extras) <= 1


def _capture_value(move):
    if move.enpassant:
        return PIECE_VALUES["p"]
    if move.pieceCaptured != ChessEngine.BLANK_SPACE:
        return PIECE_VALUES.get(move.pieceCaptured[1], 0)
    if move.pawnPromotion and move.promotionPiece:
        return PIECE_VALUES.get(move.promotionPiece[1], 0) - PIECE_VALUES["p"]
    return 0


def _order_moves(moves):
    return sorted(moves, key=_capture_value, reverse=True)


def mate_in_one_move(gs, legal):
    """Return a mating move if the side to move has one."""
    for move in legal:
        gs.makeMove(move)
        replies = gs.getValidMoves()
        check = headlessPlay.in_check(gs)
        gs.undoMove()
        if not replies and check:
            return move
    return None


def _tt_key(gs):
    ep = None
    if gs.moveLog:
        last = gs.moveLog[-1]
        if last.pieceMoved[1] == "p" and abs(last.startRow - last.endRow) == 2:
            ep = (last.endRow, last.endCol)
    return (
        tuple(tuple(row) for row in gs.board),
        gs.whiteToMove,
        gs.whiteCanCastleKing,
        gs.whiteCanCastleQueen,
        gs.blackCanCastleKing,
        gs.blackCanCastleQueen,
        ep,
    )


class SearchBot:
    """Negamax search. Params: depth (plies) and eval_fn(gs) -> int."""

    def __init__(self, depth, eval_fn, name=None, rng=None, max_nodes=None):
        if depth < 1:
            raise ValueError("depth must be >= 1")
        if not callable(eval_fn):
            raise ValueError("eval_fn must be callable")
        self.depth = depth
        self.eval_fn = eval_fn
        self.name = name if name is not None else "search-%d" % depth
        self.rng = rng if rng is not None else random.Random()
        self.max_nodes = max_nodes
        self._nodes = 0
        self._tt = {}
        self.verbose = depth >= 8

    def choose(self, gs, legal):
        if not legal:
            return None
        mate = mate_in_one_move(gs, legal)
        if mate is not None:
            return mate

        self._nodes = 0
        self._tt = {}
        ordered = _order_moves(list(legal))
        best_moves = [ordered[0]]
        started = time.time()
        for search_depth in range(1, self.depth + 1):
            if self.max_nodes is not None and self._nodes >= self.max_nodes:
                break
            try:
                _score, moves = self._root_search(gs, ordered, search_depth)
            except _NodeLimit:
                break
            if moves:
                best_moves = moves
                picked = {id(move) for move in moves}
                ordered = moves + [move for move in ordered if id(move) not in picked]
            if self.verbose:
                notation = best_moves[0].getChessNotation() if best_moves else "-"
                sys.stderr.write(
                    "%s  d=%d  nodes=%d  %.1fs  score=%d  pv=%s\n"
                    % (self.name, search_depth, self._nodes,
                       time.time() - started, _score, notation)
                )
                sys.stderr.flush()
            if _score >= MATE_SCORE - 400:
                break
        return self.rng.choice(best_moves)

    def _root_search(self, gs, legal, depth):
        best_score = -INF
        best_moves = []
        alpha = -INF
        for move in legal:
            gs.makeMove(move)
            try:
                score = -self._negamax(gs, depth - 1, -INF, -alpha, 1)
            except _NodeLimit:
                gs.undoMove()
                raise
            gs.undoMove()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
            if score > alpha:
                alpha = score
        return best_score, best_moves

    def _store_tt(self, key, depth, flag, val):
        old = self._tt.get(key)
        if old is None or old[0] <= depth:
            self._tt[key] = (depth, flag, val)

    def _negamax(self, gs, depth, alpha, beta, ply):
        self._nodes += 1
        if self.max_nodes is not None and self._nodes >= self.max_nodes:
            raise _NodeLimit()

        key = _tt_key(gs)
        cached = self._tt.get(key)
        if cached is not None:
            stored_depth, flag, val = cached
            if stored_depth >= depth:
                if flag == "exact":
                    return val
                if flag == "low" and val >= beta:
                    return val
                if flag == "high" and val <= alpha:
                    return val

        if depth == 0:
            return self.eval_fn(gs)

        legal = gs.getValidMoves()
        if not legal:
            if headlessPlay.in_check(gs):
                return -MATE_SCORE + ply
            return 0
        if _insufficient_material(gs.board):
            return 0

        orig_alpha = alpha
        best = -INF
        for move in _order_moves(legal):
            gs.makeMove(move)
            score = -self._negamax(gs, depth - 1, -beta, -alpha, ply + 1)
            gs.undoMove()
            if score > best:
                best = score
            if score > alpha:
                alpha = score
            if alpha >= beta:
                break
        if best <= orig_alpha:
            flag = "high"
        elif best >= beta:
            flag = "low"
        else:
            flag = "exact"
        self._store_tt(key, depth, flag, best)
        return best


class Search1Bot(SearchBot):
    """Alpha-beta search, depth 1, greedy material eval."""

    def __init__(self, name="search1", rng=None):
        SearchBot.__init__(self, 1, greedy_eval, name=name, rng=rng)


class Search2Bot(SearchBot):
    """Alpha-beta search, depth 2, greedy material eval."""

    def __init__(self, name="search2", rng=None):
        SearchBot.__init__(self, 2, greedy_eval, name=name, rng=rng)


class Search8ValueBot(SearchBot):
    """Alpha-beta search, full depth 8, piece-value eval. Mate in one is always played."""

    def __init__(self, name="search8value", rng=None):
        SearchBot.__init__(self, SEARCH8_DEPTH, piece_value_eval, name=name, rng=rng)


class Search8RulesBot(SearchBot):
    """Alpha-beta search, full depth 8, many positional rules. Mate in one is always played."""

    def __init__(self, name="search8rules", rng=None):
        SearchBot.__init__(self, SEARCH8_DEPTH, rules_eval, name=name, rng=rng)
