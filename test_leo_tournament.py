"""Tests for the Leo bot ranking tournament."""

import os
import random
import subprocess
import sys
import unittest

import ChessEngine
import headlessPlay
import leoTournament


class ScriptedBot:
    def __init__(self, name, tokens):
        self.name = name
        self.tokens = list(tokens)
        self.i = 0

    def choose(self, gs, legal):
        if self.i >= len(self.tokens):
            return legal[0]
        token = self.tokens[self.i]
        self.i += 1
        return headlessPlay.find_legal_move(gs, token, legal)


class ColorRecorder:
    def __init__(self, name, inner):
        self.name = name
        self.inner = inner
        self.as_white = 0
        self.as_black = 0

    def choose(self, gs, legal):
        if not gs.moveLog:
            self.as_white += 1
        elif len(gs.moveLog) == 1:
            self.as_black += 1
        return self.inner.choose(gs, legal)


class LeoRatingTests(unittest.TestCase):
    def test_equal_ratings_expect_a_draw(self):
        self.assertAlmostEqual(leoTournament.expected_score(1500, 1500), 0.5)

    def test_update_after_upset_win(self):
        ra, rb = leoTournament.update_ratings(1500, 1500, 1.0, k=32)
        self.assertAlmostEqual(ra, 1516.0)
        self.assertAlmostEqual(rb, 1484.0)

    def test_fitted_ratings_ignore_game_order(self):
        games = (
            [("a", "b", 1.0)] * 6
            + [("a", "c", 0.5)] * 6
            + [("b", "c", 0.0)] * 6
        )
        names = ["a", "b", "c"]
        forward = leoTournament.fit_leo_ratings(names, games)
        backward = leoTournament.fit_leo_ratings(names, list(reversed(games)))
        for name in names:
            self.assertAlmostEqual(forward[name], backward[name], places=5)

    def test_sweep_winner_rates_above_loser(self):
        games = [("good", "bad", 1.0)] * 20
        ratings = leoTournament.fit_leo_ratings(["good", "bad"], games)
        self.assertGreater(ratings["good"], ratings["bad"])
        self.assertAlmostEqual(
            (ratings["good"] + ratings["bad"]) / 2.0, 1500.0, places=4)

    def test_default_games_per_pair_is_1000(self):
        self.assertEqual(leoTournament.DEFAULT_GAMES, 1000)


class PlayGameTests(unittest.TestCase):
    def test_fools_mate_through_headless_game(self):
        white = ScriptedBot("white", ["f3", "g4"])
        black = ScriptedBot("black", ["e5", "Qh4"])
        result = leoTournament.play_game(white, black)
        self.assertEqual(result.white_score, 0.0)
        self.assertEqual(result.reason, "checkmate")
        self.assertEqual(result.plies, 4)

    def test_resign_bot_forfeits_on_move_one(self):
        result = leoTournament.play_game(
            leoTournament.ResignBot("resign"),
            leoTournament.FirstBot("first"),
        )
        self.assertEqual(result.white_score, 0.0)
        self.assertEqual(result.reason, "forfeit")
        self.assertEqual(result.plies, 0)

    def test_insufficient_material_is_a_draw(self):
        game = headlessPlay.HeadlessGame()
        game.gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
        game.gs.board[7][4] = "wK"
        game.gs.board[0][4] = "bK"
        game.gs.whiteCanCastleKing = False
        game.gs.whiteCanCastleQueen = False
        game.gs.blackCanCastleKing = False
        game.gs.blackCanCastleQueen = False
        result = leoTournament.play_game(
            leoTournament.FirstBot("w"),
            leoTournament.FirstBot("b"),
            game=game,
        )
        self.assertEqual(result.white_score, 0.5)
        self.assertEqual(result.reason, "insufficient")

    def test_random_bot_plays_a_legal_game(self):
        white = leoTournament.RandomBot("w", rng=random.Random(1))
        black = leoTournament.RandomBot("b", rng=random.Random(2))
        result = leoTournament.play_game(white, black, max_plies=80)
        self.assertIn(result.white_score, (0.0, 0.5, 1.0))
        self.assertGreater(result.plies, 0)


class TournamentTests(unittest.TestCase):
    def test_each_pair_plays_n_games_alternating_colors(self):
        n = 4
        inner_a = leoTournament.ResignBot("inner-a")
        inner_b = leoTournament.ResignBot("inner-b")
        a = ColorRecorder("a", inner_a)
        b = ColorRecorder("b", inner_b)
        result = leoTournament.run_tournament([a, b], n=n, k=32)
        self.assertEqual(result.n, n)
        self.assertEqual(len(result.pairs), 1)
        pair = result.pairs[0]
        self.assertEqual(pair.games, n)
        self.assertEqual(pair.white_a, n // 2)
        self.assertEqual(pair.white_b, n // 2)
        self.assertEqual(a.as_white, n // 2)
        self.assertEqual(b.as_white, n // 2)

    def test_three_bots_make_three_pairs(self):
        bots = leoTournament.make_bots(["random", "first", "resign"], seed=0)
        result = leoTournament.run_tournament(bots, n=2)
        self.assertEqual(len(result.pairs), 3)
        for pair in result.pairs:
            self.assertEqual(pair.games, 2)
        played = sum(rec.games for rec in result.records)
        self.assertEqual(played, 12)  # 3 pairs * 2 games * 2 players

    def test_random_outranks_resign(self):
        bots = leoTournament.make_bots(["random", "resign"], seed=3)
        result = leoTournament.run_tournament(bots, n=8)
        ranking = {rec.name: rec for rec in result.records}
        self.assertGreater(ranking["random"].rating, ranking["resign"].rating)
        self.assertEqual(ranking["random"].wins, 8)
        self.assertEqual(ranking["resign"].wins, 0)
        self.assertEqual(result.records[0].name, "random")

    def test_duplicate_kind_gets_unique_names(self):
        bots = leoTournament.make_bots(["random", "random"], seed=0)
        self.assertEqual([bot.name for bot in bots], ["random-1", "random-2"])
        result = leoTournament.run_tournament(bots, n=2)
        self.assertEqual(len(result.records), 2)

    def test_report_lists_ratings_and_pairs(self):
        bots = leoTournament.make_bots(["random", "resign"], seed=1)
        result = leoTournament.run_tournament(bots, n=2)
        text = leoTournament.format_report(result)
        self.assertIn("Leo rankings", text)
        self.assertIn("2 games/pair", text)
        self.assertIn("random vs resign", text)
        self.assertIn("rating", text)


class BotChoiceTests(unittest.TestCase):
    def test_capture_bot_takes_the_open_capture(self):
        gs = ChessEngine.GameState()
        gs.makeMove(headlessPlay.find_legal_move(gs, "e4"))
        gs.makeMove(headlessPlay.find_legal_move(gs, "d5"))
        legal = gs.getValidMoves()
        bot = leoTournament.CaptureBot("capture", rng=random.Random(0))
        for _ in range(12):
            move = bot.choose(gs, legal)
            self.assertNotEqual(move.pieceCaptured, ChessEngine.BLANK_SPACE)

    def test_random_bot_stays_inside_legal_moves(self):
        gs = ChessEngine.GameState()
        legal = gs.getValidMoves()
        ids = {move.moveID for move in legal}
        bot = leoTournament.RandomBot("random", rng=random.Random(0))
        for _ in range(20):
            move = bot.choose(gs, legal)
            self.assertIn(move.moveID, ids)

    def test_hunter_plays_mate_in_one(self):
        gs = ChessEngine.GameState()
        for token in ["f3", "e5", "g4"]:
            gs.makeMove(headlessPlay.find_legal_move(gs, token))
        legal = gs.getValidMoves()
        bot = leoTournament.HunterBot("hunter", rng=random.Random(0))
        move = bot.choose(gs, legal)
        gs.makeMove(move)
        self.assertEqual(gs.getValidMoves(), [])
        self.assertTrue(headlessPlay.in_check(gs))

    def test_hunter_prefers_mate_over_stalemate(self):
        gs = _bare_board()
        gs.board[2][0] = "wK"  # a6
        gs.board[2][1] = "wQ"  # b6
        gs.board[0][0] = "bK"  # a8
        legal = gs.getValidMoves()
        bot = leoTournament.HunterBot("hunter", rng=random.Random(0))
        move = bot.choose(gs, legal)
        gs.makeMove(move)
        self.assertEqual(gs.getValidMoves(), [])
        self.assertTrue(headlessPlay.in_check(gs))

    def test_hunter_does_not_take_into_insufficient_material(self):
        gs = _bare_board()
        gs.board[4][4] = "wK"  # e4
        gs.board[0][1] = "wB"  # b8
        gs.board[2][4] = "bK"  # e6
        gs.board[1][0] = "bN"  # a7
        legal = gs.getValidMoves()
        take = [m for m in legal if m.getChessNotation() == "b8a7"]
        self.assertTrue(take, "expected Bxa7 to be legal")
        bot = leoTournament.HunterBot("hunter", rng=random.Random(0))
        move = bot.choose(gs, legal)
        self.assertNotEqual(move.getChessNotation(), "b8a7")

    def test_hunter_converts_king_and_queen_vs_king(self):
        gs = _bare_board()
        gs.board[7][0] = "wK"  # a1
        gs.board[7][3] = "wQ"  # d1
        gs.board[0][0] = "bK"  # a8
        game = headlessPlay.HeadlessGame()
        game.gs = gs
        result = leoTournament.play_game(
            leoTournament.HunterBot("hunter", rng=random.Random(0)),
            leoTournament.FirstBot("first"),
            game=game,
            max_plies=80,
        )
        self.assertEqual(result.reason, "checkmate")
        self.assertEqual(result.white_score, 1.0)

    def test_hunter_has_fewer_draws_against_greedy_than_greedy_vs_itself(self):
        hunter_pair = leoTournament.run_tournament(
            leoTournament.make_bots(["hunter", "greedy"], seed=1), n=4)
        greedy_pair = leoTournament.run_tournament(
            leoTournament.make_bots(["greedy", "greedy"], seed=1), n=4)
        self.assertLess(hunter_pair.pairs[0].draws, greedy_pair.pairs[0].draws)
        ranking = {rec.name: rec for rec in hunter_pair.records}
        self.assertGreaterEqual(ranking["hunter"].wins, ranking["greedy"].wins)


def _bare_board():
    gs = ChessEngine.GameState()
    gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
    gs.whiteCanCastleKing = False
    gs.whiteCanCastleQueen = False
    gs.blackCanCastleKing = False
    gs.blackCanCastleQueen = False
    gs.moveLog = []
    return gs


class CliTests(unittest.TestCase):
    def test_cli_default_games_is_1000(self):
        proc = subprocess.run(
            [sys.executable, "leoTournament.py", "--help"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1000", proc.stdout)
        self.assertIn("games each pair plays", proc.stdout)
        self.assertEqual(leoTournament.DEFAULT_BOTS, "random,greedy,hunter")
        self.assertIn("hunter", proc.stdout)

    def test_cli_lists_hunter(self):
        proc = subprocess.run(
            [sys.executable, "leoTournament.py", "--list-bots"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("hunter", proc.stdout)
        self.assertIn("search8value", proc.stdout)
        self.assertIn("search8rules", proc.stdout)
        self.assertNotIn("search8random", proc.stdout)

    def test_cli_short_tournament(self):
        proc = subprocess.run(
            [sys.executable, "leoTournament.py", "-n", "2",
             "--bots", "random,resign", "--seed", "0", "--quiet"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Leo rankings", proc.stdout)
        self.assertIn("random", proc.stdout)
        self.assertIn("resign", proc.stdout)
        self.assertIn("2 games/pair", proc.stdout)


if __name__ == "__main__":
    unittest.main()
