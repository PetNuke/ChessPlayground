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

    def test_random_eval_still_plays_mate_in_one(self):
        gs = ChessEngine.GameState()
        for token in ["f3", "e5", "g4"]:
            gs.makeMove(headlessPlay.find_legal_move(gs, token))
        legal = gs.getValidMoves()
        bot = searchBot.SearchBot(
            8, searchBot.random_eval, rng=random.Random(0), max_nodes=50)
        move = bot.choose(gs, legal)
        gs.makeMove(move)
        self.assertEqual(gs.getValidMoves(), [])
        self.assertTrue(headlessPlay.in_check(gs))

    def test_depth_8_bots_use_requested_eval(self):
        value_bot, rules_bot = leoTournament.make_bots(
            ["search8value", "search8rules"], seed=0)
        self.assertEqual(value_bot.depth, 8)
        self.assertEqual(rules_bot.depth, 8)
        self.assertIs(value_bot.eval_fn, searchBot.piece_value_eval)
        self.assertIs(rules_bot.eval_fn, searchBot.rules_eval)
        self.assertIsNone(value_bot.max_nodes)
        self.assertIsNone(rules_bot.max_nodes)
        self.assertNotIn("search8random", leoTournament.BOT_KINDS)

    def test_search8_krk_searches_beyond_old_node_cap(self):
        gs = ChessEngine.GameState()
        gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
        gs.board[7][0] = "wK"
        gs.board[7][7] = "wR"
        gs.board[0][7] = "bK"
        gs.whiteCanCastleKing = False
        gs.whiteCanCastleQueen = False
        gs.blackCanCastleKing = False
        gs.blackCanCastleQueen = False
        gs.moveLog = []
        bot = searchBot.Search8ValueBot(rng=random.Random(0))
        move = bot.choose(gs, gs.getValidMoves())
        self.assertIsNotNone(move)
        self.assertIsNone(bot.max_nodes)
        self.assertGreater(bot._nodes, 400)

    def test_rules_eval_rewards_extra_queen_and_center(self):
        start = ChessEngine.GameState()
        extra = ChessEngine.GameState()
        extra.board[4][0] = "wQ"
        self.assertGreater(searchBot.rules_eval(extra), searchBot.rules_eval(start))
        center = ChessEngine.GameState()
        center.makeMove(headlessPlay.find_legal_move(center, "e4"))
        center.whiteToMove = True
        self.assertGreater(searchBot.rules_eval(center), searchBot.rules_eval(start))

    def test_all_kinds_are_buildable(self):
        bots = leoTournament.make_bots(["all"], seed=1)
        self.assertEqual(len(bots), len(leoTournament.BOT_KINDS))
        names = [bot.name for bot in bots]
        self.assertEqual(len(names), len(set(names)))
        self.assertIn("search8rules", names)
        self.assertIn("search8value", names)
        self.assertNotIn("search8random", names)
        self.assertIn("hunter", names)
        self.assertIn("resign", names)


if __name__ == "__main__":
    unittest.main()
