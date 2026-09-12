"""Tests for the headless text client."""

import os
import subprocess
import sys
import tempfile
import unittest

import ChessEngine
import headlessPlay


def run_lines(lines, quiet_opening=True):
    out = []
    game = headlessPlay.HeadlessGame()
    if not quiet_opening:
        out.append(headlessPlay.render_board(game.gs))
    for line in lines:
        headlessPlay.handle_line(game, line, out.append)
    return game, out


class HeadlessPlayTests(unittest.TestCase):
    def test_san_and_uci_opening(self):
        game, _ = run_lines(["e4 e5", "g1f3 Nc6"])
        self.assertTrue(game.gs.whiteToMove)
        self.assertEqual(len(game.gs.moveLog), 4)
        self.assertEqual(game.gs.board[4][4], "wp")  # e4
        self.assertEqual(game.gs.board[3][4], "bp")  # e5
        self.assertEqual(game.gs.board[5][5], "wN")  # f3
        self.assertEqual(game.gs.board[2][2], "bN")  # c6

    def test_illegal_move_rejected(self):
        game, out = run_lines(["e4", "e4"])
        self.assertTrue(any("illegal move" in line.lower() for line in out))
        self.assertEqual(len(game.gs.moveLog), 1)

    def test_undo(self):
        game, _ = run_lines(["e4 e5", "undo"])
        self.assertFalse(game.gs.whiteToMove)
        self.assertEqual(len(game.gs.moveLog), 1)
        self.assertEqual(game.gs.board[4][4], "wp")
        self.assertEqual(game.gs.board[1][4], "bp")

    def test_fools_mate(self):
        game, out = run_lines(["f3 e5 g4 Qh4"])
        self.assertIsNotNone(game.over_message)
        self.assertIn("checkmate", game.over_message.lower())
        self.assertTrue(any("checkmate" in line.lower() for line in out))
        self.assertEqual(len(game.legal_moves()), 0)

    def test_en_passant_via_text(self):
        game, out = run_lines(["e4 a6 e5 d5 exd6"])
        self.assertTrue(game.gs.moveLog[-1].enpassant)
        self.assertEqual(game.gs.board[3][3], ChessEngine.BLANK_SPACE)
        self.assertEqual(game.gs.board[2][3], "wp")
        self.assertTrue(any("en passant" in line for line in out))

    def test_castling_via_text(self):
        game, out = run_lines(["e4 e5 Nf3 Nc6 Be2 Nf6 O-O"])
        self.assertTrue(game.gs.moveLog[-1].castle)
        self.assertEqual(game.gs.board[7][6], "wK")
        self.assertEqual(game.gs.board[7][5], "wR")
        self.assertTrue(any("castle" in line for line in out))

        game2, _ = run_lines(["e4 e5 Nf3 Nc6 Be2 Nf6 e1g1"])
        self.assertTrue(game2.gs.moveLog[-1].castle)
        self.assertEqual(game2.gs.board[7][6], "wK")

    def test_promotion_via_text(self):
        game = headlessPlay.HeadlessGame()
        game.gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
        game.gs.board[1][4] = "wp"
        game.gs.board[7][4] = "wK"
        game.gs.board[0][7] = "bK"
        game.gs.whiteCanCastleKing = False
        game.gs.whiteCanCastleQueen = False
        game.gs.blackCanCastleKing = False
        game.gs.blackCanCastleQueen = False
        out = []
        headlessPlay.handle_line(game, "e8=N", out.append)
        self.assertEqual(game.gs.board[0][4], "wN")
        self.assertTrue(game.gs.moveLog[-1].pawnPromotion)

        game.undo()
        headlessPlay.handle_line(game, "e7e8q", out.append)
        self.assertEqual(game.gs.board[0][4], "wQ")

    def test_fen_and_commands(self):
        game, out = run_lines(["e4", "fen", "log", "moves"])
        self.assertTrue(any(line.startswith("rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3")
                            for line in out))
        self.assertTrue(any("1. e2e4" in line for line in out))
        self.assertTrue(any("e7e5" in line for line in out))

    def test_gundersen_faul_via_san(self):
        line = (
            "e4 e6 d4 d5 e5 c5 c3 cxd4 cxd4 Bb4+ Nc3 Nc6 "
            "Nf3 Nge7 Bd3 O-O Bxh7+ Kxh7 Ng5+ Kg6 h4 Nxd4 "
            "Qg4 f5 h5+ Kh6 Nxe6+ g5 hxg6"
        )
        game, out = run_lines([line])
        self.assertTrue(game.gs.moveLog[-1].enpassant)
        self.assertIn("checkmate", game.over_message.lower())
        self.assertTrue(any("en passant" in line for line in out))

    def test_cli_moves_flag(self):
        proc = subprocess.run(
            [sys.executable, "headlessPlay.py", "--quiet", "--moves", "f3 e5 g4 Qh4"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("checkmate", proc.stdout.lower())

    def test_cli_file_and_illegal_stop(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
            handle.write("e4 e5\nQh5 Nc6\nBc4 Nf6\nQh8\n")
            path = handle.name
        try:
            proc = subprocess.run(
                [sys.executable, "headlessPlay.py", "--quiet", "--file", path],
                cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
                capture_output=True,
                text=True,
                check=False,
            )
        finally:
            os.remove(path)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("illegal move", proc.stdout.lower())

    def test_pipe_session_quit(self):
        proc = subprocess.run(
            [sys.executable, "headlessPlay.py", "--quiet"],
            cwd=os.path.dirname(os.path.abspath(__file__)) or ".",
            input="e4\nboard\nquit\n",
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("P", proc.stdout)
        self.assertIn("Goodbye", proc.stdout)


if __name__ == "__main__":
    unittest.main()
