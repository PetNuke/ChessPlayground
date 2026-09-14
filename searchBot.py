"""
Framework for search bots: SearchBot(depth, eval_fn).

`depth` is plies of minimax (alpha-beta). `eval_fn(gs)` is a greedy-style
leaf evaluator: higher is better for the side to move.

Write a new bot by passing those two arguments:

    bot = SearchBot(depth=2, eval_fn=greedy_eval)
    bot = SearchBot(depth=3, eval_fn=my_eval, name="mine")
"""

from __future__ import annotations

import random

import ChessEngine
import headlessPlay

PIECE_VALUES = {"p": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}
MATE_SCORE = 100000
INF = 10 ** 9


def greedy_eval(gs):
    """Material score for the side to move (captures raise it)."""
    score = 0
    for row in gs.board:
        for piece in row:
            if piece == ChessEngine.BLANK_SPACE or piece[1] == "K":
                continue
            value = PIECE_VALUES.get(piece[1], 0)
            if piece[0] == "w":
                score += value
            else:
                score -= value
    return score if gs.whiteToMove else -score


def _insufficient_material(board):
    extras = []
    for row in board:
        for piece in row:
            if piece == ChessEngine.BLANK_SPACE or piece[1] == "K":
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


class SearchBot:
    """Negamax search. Params: depth (plies) and eval_fn(gs) -> int."""

    def __init__(self, depth, eval_fn, name=None, rng=None):
        if depth < 1:
            raise ValueError("depth must be >= 1")
        if not callable(eval_fn):
            raise ValueError("eval_fn must be callable")
        self.depth = depth
        self.eval_fn = eval_fn
        self.name = name if name is not None else "search-%d" % depth
        self.rng = rng if rng is not None else random.Random()

    def choose(self, gs, legal):
        if not legal:
            return None
        best_score = -INF
        best_moves = []
        for move in _order_moves(legal):
            gs.makeMove(move)
            score = -self._negamax(gs, self.depth - 1, -INF, INF, 1)
            gs.undoMove()
            if score > best_score:
                best_score = score
                best_moves = [move]
            elif score == best_score:
                best_moves.append(move)
        return self.rng.choice(best_moves)

    def _negamax(self, gs, depth, alpha, beta, ply):
        legal = gs.getValidMoves()
        if not legal:
            if headlessPlay.in_check(gs):
                return -MATE_SCORE + ply
            return 0
        if _insufficient_material(gs.board):
            return 0
        if depth == 0:
            return self.eval_fn(gs)

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
        return best


class Search1Bot(SearchBot):
    """Alpha-beta search, depth 1, greedy material eval."""

    def __init__(self, name="search1", rng=None):
        SearchBot.__init__(self, 1, greedy_eval, name=name, rng=rng)


class Search2Bot(SearchBot):
    """Alpha-beta search, depth 2, greedy material eval."""

    def __init__(self, name="search2", rng=None):
        SearchBot.__init__(self, 2, greedy_eval, name=name, rng=rng)
