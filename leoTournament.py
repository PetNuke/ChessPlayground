"""
Leo ranking tournament for ChessEngine bots, played through headlessPlay.

Each unique pair of bots plays n games (default 1000), alternating colors.
Ratings use the Elo formula (called Leo here).
"""

from __future__ import annotations

import argparse
import itertools
import random
import sys

import ChessEngine
import headlessPlay
import searchBot

DEFAULT_GAMES = 1000
DEFAULT_K = 32
DEFAULT_START = 1500
DEFAULT_MAX_PLIES = 400
FIFTY_MOVE_PLIES = 100

PIECE_VALUES = {"p": 100, "N": 320, "B": 330, "R": 500, "Q": 900, "K": 0}


class GameResult:
    def __init__(self, white_score, reason, plies):
        self.white_score = white_score  # 1.0 white win, 0.0 black win, 0.5 draw
        self.reason = reason
        self.plies = plies


class BotRecord:
    def __init__(self, name, rating):
        self.name = name
        self.rating = rating
        self.wins = 0
        self.draws = 0
        self.losses = 0

    @property
    def games(self):
        return self.wins + self.draws + self.losses

    @property
    def score(self):
        return self.wins + 0.5 * self.draws


class PairRecord:
    def __init__(self, name_a, name_b):
        self.name_a = name_a
        self.name_b = name_b
        self.wins_a = 0
        self.wins_b = 0
        self.draws = 0
        self.white_a = 0
        self.white_b = 0

    @property
    def games(self):
        return self.wins_a + self.wins_b + self.draws


class TournamentResult:
    def __init__(self, records, pairs, n, k, start):
        self.records = records
        self.pairs = pairs
        self.n = n
        self.k = k
        self.start = start


class RandomBot:
    """Picks uniformly among legal moves."""

    def __init__(self, name="random", rng=None):
        self.name = name
        self.rng = rng if rng is not None else random.Random()

    def choose(self, gs, legal):
        if not legal:
            return None
        return self.rng.choice(legal)


class CaptureBot:
    """Takes a capture when one exists, otherwise moves at random."""

    def __init__(self, name="capture", rng=None):
        self.name = name
        self.rng = rng if rng is not None else random.Random()

    def choose(self, gs, legal):
        if not legal:
            return None
        captures = [
            move for move in legal
            if move.enpassant or move.pieceCaptured != ChessEngine.BLANK_SPACE
        ]
        return self.rng.choice(captures or legal)


class GreedyBot:
    """Prefers the highest-value capture or promotion, else random."""

    def __init__(self, name="greedy", rng=None):
        self.name = name
        self.rng = rng if rng is not None else random.Random()

    def choose(self, gs, legal):
        if not legal:
            return None
        best = max(legal, key=lambda move: _material_gain(move))
        gain = _material_gain(best)
        pool = [move for move in legal if _material_gain(move) == gain]
        return self.rng.choice(pool)


class HunterBot:
    """Takes mate in one, avoids stalemate, and keeps enough material to mate."""

    def __init__(self, name="hunter", rng=None):
        self.name = name
        self.rng = rng if rng is not None else random.Random()

    def choose(self, gs, legal):
        if not legal:
            return None
        white = gs.whiteToMove
        my_mat = _material_of(gs.board, white)
        opp_mat = _material_of(gs.board, not white)
        ahead = my_mat > opp_mat
        behind = my_mat < opp_mat
        endgame = opp_mat < 400

        probed = [(move, _probe_move(gs, move, white)) for move in legal]
        mates = [move for move, out in probed if out.mate]
        if mates:
            return self.rng.choice(mates)

        playable = [(move, out) for move, out in probed if not out.stalemate]
        if not playable:
            playable = probed

        scored = []
        for move, out in playable:
            value = _material_gain(move)
            if out.check:
                value += 80 if (ahead and endgame) else 5000
            if move.pieceMoved[1] == "p" or move.pawnPromotion:
                value += 1000
            if out.approach > 0:
                value += (250 if endgame else 30) * out.approach
            if ahead:
                value -= 25 * out.replies
                value += 120 * out.opp_edge
            if out.opp_capture > _material_gain(move):
                value -= 20 * (out.opp_capture - _material_gain(move))
            if out.dead:
                if ahead:
                    value -= 50000
                elif behind:
                    value += 4000
                else:
                    value -= 2000
            scored.append((value, move))
        best = max(item[0] for item in scored)
        pool = [move for value, move in scored if value == best]
        return self.rng.choice(pool)


class FirstBot:
    """Always plays the first legal move in engine order."""

    def __init__(self, name="first", rng=None):
        self.name = name
        self.rng = rng

    def choose(self, gs, legal):
        return legal[0] if legal else None


class ResignBot:
    """Forfeits immediately. Useful as a ranking baseline in tests."""

    def __init__(self, name="resign", rng=None):
        self.name = name
        self.rng = rng

    def choose(self, gs, legal):
        return None


BOT_KINDS = {
    "random": RandomBot,
    "capture": CaptureBot,
    "greedy": GreedyBot,
    "hunter": HunterBot,
    "search1": searchBot.Search1Bot,
    "search2": searchBot.Search2Bot,
    "search7value": searchBot.Search7ValueBot,
    "search7rules": searchBot.Search7RulesBot,
    "first": FirstBot,
    "resign": ResignBot,
}

DEFAULT_BOTS = "random,greedy,hunter"
ALL_BOTS = tuple(BOT_KINDS.keys())


def _material_of(board, white):
    color = "w" if white else "b"
    total = 0
    for row in board:
        for piece in row:
            if piece[0] == color and piece[1] != "K":
                total += PIECE_VALUES.get(piece[1], 0)
    return total


def _kings(board):
    white_king = black_king = None
    for row in range(8):
        for col in range(8):
            piece = board[row][col]
            if piece == "wK":
                white_king = (row, col)
            elif piece == "bK":
                black_king = (row, col)
    return white_king, black_king


def _king_distance(a, b):
    if a is None or b is None:
        return 0
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


class _Probe:
    __slots__ = (
        "mate", "stalemate", "check", "dead",
        "approach", "opp_capture", "replies", "opp_edge",
    )

    def __init__(self, mate, stalemate, check, dead, approach, opp_capture, replies, opp_edge):
        self.mate = mate
        self.stalemate = stalemate
        self.check = check
        self.dead = dead
        self.approach = approach
        self.opp_capture = opp_capture
        self.replies = replies
        self.opp_edge = opp_edge


def _probe_move(gs, move, mover_is_white):
    before = _kings(gs.board)
    gs.makeMove(move)
    replies = gs.getValidMoves()
    check = headlessPlay.in_check(gs)
    dead = insufficient_material(gs.board)
    after = _kings(gs.board)
    opp_capture = 0
    for reply in replies:
        gain = _material_gain(reply)
        if gain > opp_capture:
            opp_capture = gain
    gs.undoMove()

    mate = len(replies) == 0 and check
    stalemate = len(replies) == 0 and not check
    if mover_is_white:
        my_before, opp_before = before
        my_after, opp_after = after
    else:
        opp_before, my_before = before
        opp_after, my_after = after
    approach = _king_distance(my_before, opp_before) - _king_distance(my_after, opp_after)
    opp_edge = 0
    if opp_after is not None:
        if opp_after[0] in (0, 7):
            opp_edge += 1
        if opp_after[1] in (0, 7):
            opp_edge += 1
    return _Probe(mate, stalemate, check, dead, approach, opp_capture, len(replies), opp_edge)


def _material_gain(move):
    captured = 0
    if move.enpassant:
        captured = PIECE_VALUES["p"]
    elif move.pieceCaptured != ChessEngine.BLANK_SPACE:
        captured = PIECE_VALUES.get(move.pieceCaptured[1], 0)
    promo = 0
    if move.pawnPromotion and move.promotionPiece:
        promo = PIECE_VALUES.get(move.promotionPiece[1], 0) - PIECE_VALUES["p"]
    return captured + promo


def expected_score(rating, opponent_rating):
    return 1.0 / (1.0 + 10 ** ((opponent_rating - rating) / 400.0))


def update_ratings(rating_a, rating_b, score_a, k=DEFAULT_K):
    """Return new (rating_a, rating_b) after one game. score_a is 1, 0.5, or 0."""
    expect_a = expected_score(rating_a, rating_b)
    new_a = rating_a + k * (score_a - expect_a)
    new_b = rating_b + k * ((1.0 - score_a) - (1.0 - expect_a))
    return new_a, new_b


def is_pawn_or_capture(move):
    return (
        move.pieceMoved[1] == "p"
        or move.enpassant
        or move.pieceCaptured != ChessEngine.BLANK_SPACE
    )


def insufficient_material(board):
    extras = []
    for row in board:
        for piece in row:
            if piece == ChessEngine.BLANK_SPACE or piece[1] == "K":
                continue
            if piece[1] not in ("N", "B"):
                return False
            extras.append(piece)
    return len(extras) <= 1


def resolve_move(chosen, legal):
    """Map a bot's returned move onto an engine legal move, or None."""
    if chosen is None:
        return None
    for move in legal:
        if chosen is move:
            return move
    for move in legal:
        if (move.startRow, move.startCol, move.endRow, move.endCol) != (
                chosen.startRow, chosen.startCol, chosen.endRow, chosen.endCol):
            continue
        if move.pawnPromotion:
            chosen_piece = getattr(chosen, "promotionPiece", None)
            if chosen_piece == move.promotionPiece:
                return move
            if chosen_piece is None and move.promotionPiece and move.promotionPiece[1] == "Q":
                return move
            continue
        return move
    return None


def _result_from_status(game, plies):
    kind, _message = headlessPlay.game_status(game.gs)
    if kind == "checkmate":
        # Side to move is mated, so the side that just played won.
        white_score = 0.0 if game.gs.whiteToMove else 1.0
        return GameResult(white_score, "checkmate", plies)
    if kind == "stalemate":
        return GameResult(0.5, "stalemate", plies)
    if game.resigned:
        white_score = 0.0 if game.gs.whiteToMove else 1.0
        return GameResult(white_score, "resign", plies)
    return None


def play_game(white_bot, black_bot, max_plies=DEFAULT_MAX_PLIES,
              fifty_move_plies=FIFTY_MOVE_PLIES, game=None):
    """Play one game on a HeadlessGame. Returns GameResult."""
    if game is None:
        game = headlessPlay.HeadlessGame()
    halfmove = 0
    for plies in range(max_plies):
        finished = _result_from_status(game, plies)
        if finished is not None:
            return finished
        if insufficient_material(game.gs.board):
            return GameResult(0.5, "insufficient", plies)
        if halfmove >= fifty_move_plies:
            return GameResult(0.5, "fifty-move", plies)

        legal = game.legal_moves()
        if not legal:
            game.refresh_status()
            finished = _result_from_status(game, plies)
            return finished or GameResult(0.5, "stalemate", plies)

        bot = white_bot if game.gs.whiteToMove else black_bot
        try:
            chosen = bot.choose(game.gs, legal)
        except Exception:
            white_score = 0.0 if game.gs.whiteToMove else 1.0
            return GameResult(white_score, "forfeit", plies)

        move = resolve_move(chosen, legal)
        if move is None:
            white_score = 0.0 if game.gs.whiteToMove else 1.0
            return GameResult(white_score, "forfeit", plies)

        game.gs.makeMove(move)
        game.refresh_status()
        if is_pawn_or_capture(move):
            halfmove = 0
        else:
            halfmove += 1

    return GameResult(0.5, "max-plies", max_plies)


def _tally_result(record_a, record_b, pair, white_is_a, result):
    if white_is_a:
        pair.white_a += 1
        score_a = result.white_score
    else:
        pair.white_b += 1
        score_a = 1.0 - result.white_score

    if score_a == 1.0:
        record_a.wins += 1
        record_b.losses += 1
        pair.wins_a += 1
    elif score_a == 0.0:
        record_a.losses += 1
        record_b.wins += 1
        pair.wins_b += 1
    else:
        record_a.draws += 1
        record_b.draws += 1
        pair.draws += 1
    return score_a


def fit_leo_ratings(names, games, start=DEFAULT_START, k=DEFAULT_K, iterations=80):
    """
    Order-independent Leo ratings for a completed tournament.

    `games` is a list of (name_a, name_b, score_a) with score_a in {1, 0.5, 0}.
    Ratings are mean-centered on `start`. `k` is the fitting step size.
    """
    ratings = {name: float(start) for name in names}
    played = {name: 0 for name in names}
    for name_a, name_b, _score in games:
        played[name_a] += 1
        played[name_b] += 1
    if not games:
        return ratings

    for _ in range(iterations):
        deltas = {name: 0.0 for name in names}
        for name_a, name_b, score_a in games:
            expect_a = expected_score(ratings[name_a], ratings[name_b])
            deltas[name_a] += score_a - expect_a
            deltas[name_b] += (1.0 - score_a) - (1.0 - expect_a)
        largest = 0.0
        for name in names:
            if played[name] == 0:
                continue
            step = k * deltas[name] / float(played[name])
            ratings[name] += step
            largest = max(largest, abs(step))
        mean = sum(ratings[name] for name in names) / float(len(names))
        shift = start - mean
        for name in names:
            ratings[name] += shift
        if largest < 0.01:
            break
    return ratings


def play_pair(bot_a, bot_b, n=DEFAULT_GAMES, start=DEFAULT_START,
              max_plies=DEFAULT_MAX_PLIES, records=None, progress=None,
              pair_index=1, pair_count=1):
    """Play n games between two bots. bot_a is white on even game indices."""
    if records is None:
        records = {
            bot_a.name: BotRecord(bot_a.name, start),
            bot_b.name: BotRecord(bot_b.name, start),
        }
    pair = PairRecord(bot_a.name, bot_b.name)
    record_a = records[bot_a.name]
    record_b = records[bot_b.name]
    games = []
    for i in range(n):
        white_is_a = (i % 2 == 0)
        if white_is_a:
            white_bot, black_bot = bot_a, bot_b
        else:
            white_bot, black_bot = bot_b, bot_a
        result = play_game(white_bot, black_bot, max_plies=max_plies)
        score_a = _tally_result(record_a, record_b, pair, white_is_a, result)
        games.append((bot_a.name, bot_b.name, score_a))
        if progress is not None:
            progress(pair_index, pair_count, i + 1, n, bot_a, bot_b, result)
    return pair, games


def run_tournament(bots, n=DEFAULT_GAMES, k=DEFAULT_K, start=DEFAULT_START,
                   max_plies=DEFAULT_MAX_PLIES, progress=None):
    if len(bots) < 2:
        raise ValueError("need at least two bots")
    names = [bot.name for bot in bots]
    if len(names) != len(set(names)):
        raise ValueError("bot names must be unique")

    records = {bot.name: BotRecord(bot.name, start) for bot in bots}
    pairs = []
    all_games = []
    pair_list = list(itertools.combinations(bots, 2))
    pair_count = len(pair_list)
    for index, (bot_a, bot_b) in enumerate(pair_list, start=1):
        pair, games = play_pair(
            bot_a, bot_b, n=n, start=start, max_plies=max_plies,
            records=records, progress=progress,
            pair_index=index, pair_count=pair_count)
        pairs.append(pair)
        all_games.extend(games)

    fitted = fit_leo_ratings(names, all_games, start=start, k=k)
    for rec in records.values():
        rec.rating = fitted[rec.name]

    ranking = sorted(
        records.values(),
        key=lambda rec: (-rec.rating, -rec.score, rec.name),
    )
    return TournamentResult(ranking, pairs, n, k, start)


def format_report(result):
    lines = [
        "Leo rankings  (start %s, K=%s, %s games/pair)"
        % (result.start, result.k, result.n),
        "",
        "  #   rating      W     D     L   score  name",
    ]
    for index, rec in enumerate(result.records, start=1):
        lines.append(
            "%3d  %7.1f  %5d %5d %5d  %6.1f  %s"
            % (index, rec.rating, rec.wins, rec.draws, rec.losses,
               rec.score, rec.name)
        )
    lines.append("")
    lines.append("Pair results  (A-B-D, A=first name)")
    for pair in result.pairs:
        lines.append(
            "  %s vs %s  %d-%d-%d  (%d games, %s white %d / %s white %d)"
            % (pair.name_a, pair.name_b, pair.wins_a, pair.wins_b, pair.draws,
               pair.games, pair.name_a, pair.white_a, pair.name_b, pair.white_b)
        )
    return "\n".join(lines)


def make_bots(kinds, seed=0):
    """Build uniquely named bots from kind strings such as ['random', 'capture']."""
    if list(kinds) == ["all"]:
        kinds = list(ALL_BOTS)
    counts = {}
    for kind in kinds:
        if kind not in BOT_KINDS:
            raise ValueError(
                "unknown bot %r (choose from: %s)"
                % (kind, ", ".join(sorted(BOT_KINDS)))
            )
        counts[kind] = counts.get(kind, 0) + 1

    used = {}
    bots = []
    for kind in kinds:
        used[kind] = used.get(kind, 0) + 1
        if counts[kind] == 1:
            name = kind
        else:
            name = "%s-%d" % (kind, used[kind])
        rng = random.Random("%s:%s" % (seed, name))
        bots.append(BOT_KINDS[kind](name=name, rng=rng))
    return bots


def _progress_printer(out):
    def progress(pair_index, pair_count, game_index, n, bot_a, bot_b, result):
        step = max(1, n // 10)
        if game_index == 1 or game_index == n or game_index % step == 0:
            out("pair %d/%d  game %d/%d  %s vs %s  (%s, %.1f for white)"
                % (pair_index, pair_count, game_index, n,
                   bot_a.name, bot_b.name, result.reason, result.white_score))
    return progress


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Run a Leo (Elo) round-robin of ChessEngine bots.")
    parser.add_argument(
        "-n", "--games", type=int, default=DEFAULT_GAMES,
        help="games each pair plays (default: %s)" % DEFAULT_GAMES)
    parser.add_argument(
        "--bots", default=DEFAULT_BOTS,
        help="comma-separated bot kinds, or 'all' (%s)"
        % ", ".join(sorted(BOT_KINDS)))
    parser.add_argument("--seed", type=int, default=0, help="RNG seed")
    parser.add_argument(
        "--k", type=float, default=DEFAULT_K,
        help="Leo fitting step size (default: %s)" % DEFAULT_K)
    parser.add_argument(
        "--start", type=float, default=DEFAULT_START, help="starting rating")
    parser.add_argument(
        "--max-plies", type=int, default=DEFAULT_MAX_PLIES,
        help="draw if a game reaches this many half-moves")
    parser.add_argument("--quiet", action="store_true", help="no progress lines")
    parser.add_argument(
        "--list-bots", action="store_true", help="print built-in bot kinds and exit")
    args = parser.parse_args(argv)

    if args.list_bots:
        for kind in sorted(BOT_KINDS):
            print("%s  %s" % (kind, BOT_KINDS[kind].__doc__.strip().splitlines()[0]))
        return 0

    if args.games < 1:
        parser.error("--games must be >= 1")

    kinds = [part.strip() for part in args.bots.split(",") if part.strip()]
    try:
        bots = make_bots(kinds, seed=args.seed)
    except ValueError as err:
        parser.error(str(err))

    progress = None if args.quiet else _progress_printer(lambda text: print(text, file=sys.stderr))
    result = run_tournament(
        bots, n=args.games, k=args.k, start=args.start,
        max_plies=args.max_plies, progress=progress)
    print(format_report(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
