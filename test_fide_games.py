"""Replay 1000 FIDE Olympiad games through ChessEngine."""

import os
import unittest

import ChessEngine
import headlessPlay
import pgnutil

PGN_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "testdata", "fide_olympiad_2024_1000.pgn")
EXPECTED_GAMES = 1000


def load_fide_games():
    with open(PGN_PATH, encoding="utf-8") as handle:
        text = handle.read()
    games = pgnutil.split_games(text)
    parsed = []
    for raw in games:
        headers = pgnutil.game_headers(raw)
        tokens = pgnutil.movetext_tokens(pgnutil.game_movetext(raw))
        parsed.append((headers, tokens))
    return parsed


def replay_tokens(tokens):
    gs = ChessEngine.GameState()
    for index, san in enumerate(tokens, start=1):
        move = headlessPlay.find_legal_move(gs, san)
        gs.makeMove(move)
    return gs


class FideOlympiadReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = load_fide_games()

    def test_collection_has_1000_fide_olympiad_games(self):
        self.assertTrue(os.path.isfile(PGN_PATH), PGN_PATH)
        self.assertEqual(len(self.games), EXPECTED_GAMES)
        for headers, tokens in self.games:
            self.assertEqual(headers.get("Event"), "45th Olympiad 2024")
            self.assertEqual(headers.get("Site"), "Budapest HUN")
            self.assertTrue(headers.get("WhiteFideId") or headers.get("BlackFideId"))
            self.assertGreaterEqual(len(tokens), 10)

    def test_replay_all_1000_games(self):
        failures = []
        for i, (headers, tokens) in enumerate(self.games, start=1):
            label = "#%d %s" % (i, pgnutil.describe_game(headers))
            try:
                replay_tokens(tokens)
            except Exception as err:
                failures.append("%s: %s" % (label, err))
                if len(failures) >= 10:
                    break
        if failures:
            self.fail("%d game(s) failed to replay:\n%s"
                      % (len(failures), "\n".join(failures)))


if __name__ == "__main__":
    unittest.main()
