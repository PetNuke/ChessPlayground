"""Tests for SearchBot(depth, eval_fn)."""

import random
import unittest

import ChessEngine
import headlessPlay
import leoTournament
import searchBot


class SearchBotTests(unittest.TestCase):
    def test_depth_must_be_at_least_one(self):
        with self.assertRaises(ValueError):
            searchBot.SearchBot(0, searchBot.greedy_eval)

    def test_depth_1_greedy_takes_the_hanging_pawn(self):
        gs = ChessEngine.GameState()
        gs.makeMove(headlessPlay.find_legal_move(gs, "e4"))
        gs.makeMove(headlessPlay.find_legal_move(gs, "d5"))
        legal = gs.getValidMoves()
        bot = searchBot.SearchBot(1, searchBot.greedy_eval, rng=random.Random(0))
        move = bot.choose(gs, legal)
        self.assertNotEqual(move.pieceCaptured, ChessEngine.BLANK_SPACE)

    def test_depth_1_finds_mate_in_one(self):
        gs = ChessEngine.GameState()
        for token in ["f3", "e5", "g4"]:
            gs.makeMove(headlessPlay.find_legal_move(gs, token))
        legal = gs.getValidMoves()
        bot = searchBot.SearchBot(1, searchBot.greedy_eval, rng=random.Random(0))
        move = bot.choose(gs, legal)
        gs.makeMove(move)
        self.assertEqual(gs.getValidMoves(), [])
        self.assertTrue(headlessPlay.in_check(gs))

    def test_depth_2_avoids_fools_mate_blunder(self):
        gs = ChessEngine.GameState()
        gs.makeMove(headlessPlay.find_legal_move(gs, "f3"))
        gs.makeMove(headlessPlay.find_legal_move(gs, "e5"))
        legal = gs.getValidMoves()
        bot = searchBot.SearchBot(2, searchBot.greedy_eval, rng=random.Random(0))
        move = bot.choose(gs, legal)
        self.assertNotEqual(move.getChessNotation(), "g2g4")

    def test_custom_eval_fn_is_used(self):
        seen = []

        def only_a4(gs):
            seen.append(True)
            white_bonus = 100 if gs.board[4][0] == "wp" else 0
            return white_bonus if gs.whiteToMove else -white_bonus

        gs = ChessEngine.GameState()
        legal = gs.getValidMoves()
        bot = searchBot.SearchBot(1, only_a4, rng=random.Random(0))
        move = bot.choose(gs, legal)
        self.assertTrue(seen)
        self.assertEqual(move.getChessNotation(), "a2a4")

    def test_registered_search1_kind(self):
        bots = leoTournament.make_bots(["search1", "resign"], seed=0)
        self.assertEqual(bots[0].depth, 1)
        self.assertIs(bots[0].eval_fn, searchBot.greedy_eval)
        result = leoTournament.run_tournament(bots, n=2)
        ranking = {rec.name: rec for rec in result.records}
        self.assertEqual(ranking["search1"].wins, 2)


if __name__ == "__main__":
    unittest.main()
