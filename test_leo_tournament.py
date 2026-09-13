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
