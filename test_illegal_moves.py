"""Reject a wide set of illegal moves; the position must not change."""

import unittest

import ChessEngine
import headlessPlay


BLANK = ChessEngine.BLANK_SPACE


def play(moves):
    gs = ChessEngine.GameState()
    for token in moves:
        gs.makeMove(headlessPlay.find_legal_move(gs, token))
    return gs


def place(pieces, white_to_move=True, castle=False):
    """pieces: map of algebraic square -> 'wK'/'bp'/..."""
    gs = ChessEngine.GameState()
    gs.board = [[BLANK] * 8 for _ in range(8)]
    gs.whiteToMove = white_to_move
    gs.whiteCanCastleKing = castle
    gs.whiteCanCastleQueen = castle
    gs.blackCanCastleKing = castle
    gs.blackCanCastleQueen = castle
    gs.moveLog = []
    for square, piece in pieces.items():
        row = ChessEngine.Move.ranksToRows[square[1]]
        col = ChessEngine.Move.filesToCols[square[0]]
        gs.board[row][col] = piece
    return gs


def snapshot(gs):
    return (
        [row[:] for row in gs.board],
        gs.whiteToMove,
        len(gs.moveLog),
        gs.whiteCanCastleKing,
        gs.whiteCanCastleQueen,
        gs.blackCanCastleKing,
        gs.blackCanCastleQueen,
    )


class IllegalMoveTests(unittest.TestCase):
    def assertIllegal(self, gs, tokens):
        before = snapshot(gs)
        legal_uci = {m.getChessNotation() for m in gs.getValidMoves()}
        for token in tokens:
            with self.subTest(token=token):
                with self.assertRaises(headlessPlay.MoveError):
                    headlessPlay.find_legal_move(gs, token)
                uci = headlessPlay.parse_uci(token)
                if uci is not None:
                    start, end, promo = uci
                    fake = ChessEngine.Move(start, end, gs.board)
                    notation = fake.getChessNotation()
                    if promo:
                        notation += promo.lower()
                    self.assertNotIn(notation, legal_uci)
                self.assertEqual(snapshot(gs), before)

    def test_start_position_rejects_wrong_side_and_impossible_piece_moves(self):
        gs = ChessEngine.GameState()
        self.assertIllegal(gs, [
            "e5", "d5", "Nf6", "Nc6", "Qh4", "Qh5", "Ke2", "Kd2", "O-O", "O-O-O",
            "a2a1", "a2b3", "e2e5", "e2d3", "e2d4", "e2e1",
            "Nb1d2", "Nb1c2", "Nb1a1", "Ng1e2", "Ng1g3",
            "Ra1a2", "Ra1b1", "Ra1a3", "Rh1h3", "Rh1g1",
            "Bf1c4", "Bf1a6", "Bf1e2", "Bc1a3", "Bc1d2",
            "Qd1d2", "Qd1d3", "Qd1h5", "Qd1a4", "Qd1e2",
            "Ke1e2", "Ke1d1", "Ke1d2", "Ke1f1", "Ke1f2",
            "h2h5", "a7a5", "e7e5", "h8h1", "e1e8", "d1d8",
            "b1b3", "g1g3", "c2c5", "xyz", "e9e4", "e2",
        ])

    def test_quiet_san_does_not_match_a_capture(self):
        """'e5' is not dxe5; a capture SAN needs 'x'."""
        gs = play(["d4", "e5"])
        self.assertIllegal(gs, ["e5", "exd5", "dxe4", "d5e5"])
        capture = headlessPlay.find_legal_move(gs, "dxe5")
        self.assertEqual(capture.getChessNotation(), "d4e5")

        gs = play(["Nf3", "e5"])
        self.assertIllegal(gs, ["e5"])
        capture = headlessPlay.find_legal_move(gs, "Nxe5")
        self.assertEqual(capture.getChessNotation(), "f3e5")

    def test_cannot_replay_or_push_the_same_pawn_again(self):
        gs = play(["e4"])
        self.assertIllegal(gs, ["e4", "e2e4", "e4e5", "e4e6", "e5e7", "e7e4", "a2a4"])

    def test_pawn_cannot_capture_forward_or_move_diagonally_without_capture(self):
        gs = play(["e4", "e5"])
        self.assertIllegal(gs, [
            "e4e5", "e4d5", "e4f5", "e4e3", "d2e3", "f2e3", "O-O",
        ])

    def test_pawn_double_step_only_from_rank_2(self):
        gs = play(["e3", "e6"])
        self.assertIllegal(gs, ["e3e5", "e2e4", "e3d4", "e3f4"])

    def test_pawn_cannot_advance_into_or_over_an_occupied_file(self):
        gs = play(["e4", "e5", "d4", "d5"])
        self.assertIllegal(gs, ["e4e5", "d4d5", "d4d6", "e4e6"])

    def test_cannot_capture_own_pieces(self):
        gs = ChessEngine.GameState()
        self.assertIllegal(gs, [
            "Qxd2", "Bxe2", "Nxd2", "Kxd1", "Kxe2",
            "a1a2", "a1b1", "d1d2", "e1d1", "e1d2", "e1e2", "e1f1",
        ])
        gs = play(["e4", "d5"])
        self.assertIllegal(gs, ["Qxe4", "Bxe4", "Nxe4", "Kxe4"])

    def test_sliding_pieces_cannot_jump_over_pawns(self):
        gs = ChessEngine.GameState()
        self.assertIllegal(gs, [
            "d1d3", "d1d4", "d1d8", "a1a3", "a1a4", "a1a8",
            "h1h4", "h1h8", "c1e3", "c1f4", "c1h6", "c1a3",
            "f1h3", "f1a6", "Qd3", "Qd4", "Ra3", "Rh4", "Ba3", "Bh3",
        ])

    def test_bishop_rook_queen_must_use_their_own_geometry(self):
        gs = play(["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"])
        self.assertIllegal(gs, [
            "c4c5", "c4c3", "c4d4", "c4b4", "c4e4", "c4c2", "c4a4",
            "c4d6", "c4e3", "c4b6", "c4a5", "Ra3", "Rh4", "Rd2", "Nb5", "Nd1",
        ])

    def test_knight_cannot_slide_or_move_as_king(self):
        gs = play(["Nf3", "Nc6"])
        self.assertIllegal(gs, [
            "f3f4", "f3f5", "f3e3", "f3g3", "f3d3", "f3h3",
            "f3d5", "f3h5", "f3c3", "f3a3", "f3f2", "Ng1g3",
        ])

    def test_king_cannot_move_two_squares_except_castling(self):
        gs = play(["e4", "e5", "Nf3", "Nc6", "Be2", "Nf6"])
        self.assertIllegal(gs, ["Ke3", "Kd2", "Kf2", "Ke1e3", "Ke1c2", "O-O-O"])

    def test_castling_blocked_by_pieces_at_start(self):
        gs = ChessEngine.GameState()
        self.assertIllegal(gs, ["O-O", "O-O-O", "e1g1", "e1c1", "0-0", "0-0-0"])

    def test_cannot_castle_after_king_moved(self):
        gs = play(["e4", "e5", "Nf3", "Nc6", "Be2", "Nf6", "Kf1", "Be7", "Ke1", "O-O"])
        self.assertIllegal(gs, ["O-O", "O-O-O", "e1g1", "e1c1"])

    def test_cannot_castle_after_rook_moved_and_returned(self):
        gs = play(["e4", "e5", "Nf3", "Nc6", "Be2", "Nf6", "Rg1", "Be7", "Rh1", "O-O"])
        self.assertIllegal(gs, ["O-O", "e1g1"])

    def test_cannot_castle_through_check(self):
        gs = place({
            "e1": "wK", "h1": "wR", "a1": "wR",
            "e8": "bK",
            "a6": "bB",
        }, white_to_move=True, castle=True)
        self.assertIllegal(gs, ["O-O", "e1g1"])

    def test_cannot_castle_into_check(self):
        gs = place({
            "e1": "wK", "h1": "wR",
            "e8": "bK",
            "a7": "bB",
        }, white_to_move=True, castle=True)
        self.assertIllegal(gs, ["O-O", "e1g1"])

    def test_cannot_castle_out_of_check(self):
        gs = place({
            "e1": "wK", "h1": "wR", "a1": "wR",
            "e8": "bK", "e4": "bR",
        }, white_to_move=True, castle=True)
        self.assertIllegal(gs, ["O-O", "O-O-O", "e1g1", "e1c1"])

    def test_cannot_castle_queenside_through_occupied_squares(self):
        gs = play(["d4", "d5", "Bf4", "Nc6", "Qd2", "Nf6", "e3", "e6"])
        self.assertIllegal(gs, ["O-O-O", "e1c1"])

    def test_must_resolve_check(self):
        gs = play(["e4", "d5", "Bb5"])
        self.assertTrue(headlessPlay.in_check(gs))
        self.assertIllegal(gs, [
            "Nf6", "a6", "h6", "Be7", "e6", "f6", "Qe7", "Qf6",
            "O-O", "Nh6", "Na6", "b6", "g6", "h5", "a5",
        ])

    def test_cannot_move_pinned_knight_off_the_pin(self):
        gs = place({
            "e1": "wK", "b5": "wB",
            "e8": "bK", "c6": "bN",
        }, white_to_move=False)
        self.assertIllegal(gs, [
            "Na5", "Na7", "Nb4", "Nb8", "Nd4", "Nd8", "Ne5", "Ne7",
            "Nc5", "Nb6", "a5", "O-O",
        ])

    def test_cannot_walk_king_into_check(self):
        gs = place({
            "e3": "wK",
            "a4": "bR",
            "a8": "bK",
        })
        self.assertIllegal(gs, ["Ke4", "Kd4", "Kf4", "Ke3e4"])

    def test_kings_cannot_touch(self):
        gs = place({
            "e4": "wK",
            "e6": "bK",
        })
        self.assertIllegal(gs, ["Ke5", "Kd5", "Kf5", "Ke4e5"])

    def test_king_cannot_capture_protected_piece(self):
        gs = place({
            "e4": "wK",
            "d5": "bp",
            "e8": "bK",
            "d8": "bR",
        })
        self.assertIllegal(gs, ["Kxd5", "e4d5"])

    def test_en_passant_only_on_the_next_move(self):
        gs = play(["e4", "a6", "e5", "d5", "a3", "Nc6"])
        self.assertIllegal(gs, ["exd6", "e5d6", "e5c6"])

    def test_en_passant_requires_adjacent_double_push(self):
        gs = play(["e4", "a6", "e5", "c5"])
        self.assertIllegal(gs, ["exd6", "exf6", "e5d6", "e5c6", "dxc6"])

    def test_en_passant_not_allowed_on_single_step_pawn(self):
        gs = play(["e4", "d6", "e5", "d5"])
        self.assertIllegal(gs, ["exd6", "e5d6"])

    def test_cannot_en_passant_from_the_wrong_file(self):
        gs = play(["e4", "a6", "e5", "d5"])
        self.assertIllegal(gs, ["dxe6", "cxd6", "fxe6", "exd5"])

    def test_promotion_only_from_the_seventh_rank(self):
        gs = place({
            "e6": "wp",
            "e1": "wK",
            "a8": "bK",
        })
        self.assertIllegal(gs, ["e8=Q", "e7e8q", "e6e8", "e6e8q", "e5=Q"])

    def test_cannot_promote_an_empty_square_or_non_pawn(self):
        gs = play(["e4", "e5"])
        self.assertIllegal(gs, ["e8=Q", "e1=Q", "e7e8q", "Qe8=Q"])

    def test_no_moves_in_stalemate(self):
        gs = place({
            "a6": "wK",
            "c7": "wQ",
            "a8": "bK",
        }, white_to_move=False)
        self.assertFalse(headlessPlay.in_check(gs))
        self.assertEqual(gs.getValidMoves(), [])
        self.assertIllegal(gs, ["Kb8", "Ka7", "Kb7", "a5", "a8b8"])

    def test_no_moves_after_checkmate(self):
        gs = play(["f3", "e5", "g4", "Qh4"])
        self.assertEqual(gs.getValidMoves(), [])
        self.assertIllegal(gs, [
            "e3", "Nf3", "Ke2", "g5", "f4", "Qe2", "Nc3", "a3", "O-O",
        ])
        game = headlessPlay.HeadlessGame()
        for token in ["f3", "e5", "g4", "Qh4"]:
            game.play_token(token)
        self.assertIsNotNone(game.over_message)
        with self.assertRaises(headlessPlay.MoveError):
            game.play_token("e3")
        self.assertEqual(len(game.gs.moveLog), 4)

    def test_garbage_and_off_board_tokens_are_illegal(self):
        gs = ChessEngine.GameState()
        self.assertIllegal(gs, [
            "castle", "resigns", "e2e9", "i2i4", "e0e4", "e2e4q",
            "O-O-O-O", "N", "P", "00", "e4e4",
        ])

    def test_headless_session_rejects_illegal_batch_and_stops(self):
        out = []
        game = headlessPlay.HeadlessGame()
        headlessPlay.handle_line(game, "e4 e5 e4", out.append)
        self.assertEqual(len(game.gs.moveLog), 2)
        self.assertTrue(any("illegal move" in line.lower() for line in out))
        self.assertTrue(game.gs.whiteToMove)


if __name__ == "__main__":
    unittest.main()
