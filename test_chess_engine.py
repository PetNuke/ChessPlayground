"""Replay documented games and unit-test en passant, promotion, and castling."""

import re
import unittest

import ChessEngine


FILES = ChessEngine.Move.filesToCols
RANKS = ChessEngine.Move.ranksToRows


def pgn_tokens(movetext):
    movetext = re.sub(r"\{[^}]*\}", " ", movetext)
    movetext = re.sub(r"\([^)]*\)", " ", movetext)
    tokens = []
    for raw in movetext.split():
        if raw in ("1-0", "0-1", "1/2-1/2", "*"):
            break
        token = re.sub(r"^\d+\.+", "", raw)
        token = token.replace("!", "").replace("?", "")
        if token:
            tokens.append(token)
    return tokens


def strip_check(san):
    return san.replace("+", "").replace("#", "")


def move_matches_san(move, san):
    san = strip_check(san)
    if san in ("O-O", "0-0"):
        return move.castle and move.endCol == 6
    if san in ("O-O-O", "0-0-0"):
        return move.castle and move.endCol == 2

    promotion = None
    if "=" in san:
        san, promotion = san.split("=", 1)
        promotion = promotion[0].upper()
    elif len(san) >= 3 and san[-1] in "QRBN" and san[-2] in "12345678":
        # LAN-style e8Q
        promotion = san[-1]
        san = san[:-1]

    san_no_x = san.replace("x", "")
    dest = san_no_x[-2:]
    dest_file, dest_rank = dest[0], dest[1]
    if dest_file not in FILES or dest_rank not in RANKS:
        return False
    if move.endCol != FILES[dest_file] or move.endRow != RANKS[dest_rank]:
        return False

    if promotion:
        return bool(move.pawnPromotion and move.promotionPiece and move.promotionPiece[1] == promotion)

    prefix = san_no_x[:-2]
    if prefix and prefix[0] in "KQRBN":
        piece = prefix[0]
        disambig = prefix[1:]
    else:
        piece = "p"
        disambig = prefix

    if move.pieceMoved[1] != piece:
        return False

    if len(disambig) == 1:
        ch = disambig[0]
        if ch in FILES:
            return move.startCol == FILES[ch]
        if ch in RANKS:
            return move.startRow == RANKS[ch]
        return False
    if len(disambig) == 2:
        return move.startCol == FILES[disambig[0]] and move.startRow == RANKS[disambig[1]]
    return True


def play_pgn(movetext):
    gs = ChessEngine.GameState()
    played = []
    for i, san in enumerate(pgn_tokens(movetext), start=1):
        legal = gs.getValidMoves()
        matches = [m for m in legal if move_matches_san(m, san)]
        if len(matches) != 1:
            raise AssertionError(
                "Move %s (%s) matched %s legal moves: %s (legal: %s)"
                % (i, san, len(matches),
                   [m.getChessNotation() for m in matches],
                   [m.getChessNotation() for m in legal])
            )
        move = matches[0]
        gs.makeMove(move)
        played.append(move)
    return gs, played


class EnPassantTests(unittest.TestCase):
    def test_black_enpassant_removes_captured_pawn(self):
        gs = ChessEngine.GameState()
        for san in ["d3", "e5", "d4", "e4", "f4"]:
            gs.makeMove(self._unique(gs, san))
        gs.makeMove(self._unique(gs, "exf3"))
        self.assertEqual(gs.board[4][5], ChessEngine.BLANK_SPACE)  # f4 gone
        self.assertEqual(gs.board[5][5], "bp")  # f3

    def test_white_enpassant_removes_captured_pawn(self):
        gs = ChessEngine.GameState()
        for san in ["e4", "a6", "e5", "d5"]:
            gs.makeMove(self._unique(gs, san))

        legal = gs.getValidMoves()
        ep = [m for m in legal if m.enpassant]
        self.assertEqual(len(ep), 1, [m.getChessNotation() for m in legal])
        gs.makeMove(ep[0])

        # Black d-pawn on d5 must be gone; white pawn sits on d6
        self.assertEqual(gs.board[3][3], ChessEngine.BLANK_SPACE)  # d5
        self.assertEqual(gs.board[2][3], "wp")  # d6
        self.assertEqual(gs.board[4][4], ChessEngine.BLANK_SPACE)  # e5 vacated

    def test_enpassant_inferred_from_click_move(self):
        gs = ChessEngine.GameState()
        for san in ["e4", "a6", "e5", "d5"]:
            gs.makeMove(self._unique(gs, san))

        click = ChessEngine.Move((3, 4), (2, 3), gs.board)  # e5 to d6
        self.assertFalse(click.enpassant)
        gs.makeMove(click)
        self.assertTrue(click.enpassant)
        self.assertEqual(gs.board[3][3], ChessEngine.BLANK_SPACE)
        self.assertEqual(gs.board[2][3], "wp")

    def test_undo_restores_enpassant_capture(self):
        gs = ChessEngine.GameState()
        for san in ["e4", "a6", "e5", "d5"]:
            gs.makeMove(self._unique(gs, san))
        before = [row[:] for row in gs.board]
        gs.makeMove(self._unique(gs, "exd6"))
        gs.undoMove()
        self.assertEqual(gs.board, before)
        self.assertTrue(gs.whiteToMove)

    def _unique(self, gs, san):
        matches = [m for m in gs.getValidMoves() if move_matches_san(m, san)]
        self.assertEqual(len(matches), 1, san)
        return matches[0]


class CastlingTests(unittest.TestCase):
    def test_white_kingside_moves_rook(self):
        gs = ChessEngine.GameState()
        for san in ["e4", "e5", "Nf3", "Nc6", "Be2", "Nf6"]:
            matches = [m for m in gs.getValidMoves() if move_matches_san(m, san)]
            self.assertEqual(len(matches), 1, san)
            gs.makeMove(matches[0])
        matches = [m for m in gs.getValidMoves() if move_matches_san(m, "O-O")]
        self.assertEqual(len(matches), 1)
        gs.makeMove(matches[0])
        self.assertEqual(gs.board[7][6], "wK")
        self.assertEqual(gs.board[7][5], "wR")
        self.assertEqual(gs.board[7][4], ChessEngine.BLANK_SPACE)
        self.assertEqual(gs.board[7][7], ChessEngine.BLANK_SPACE)
        self.assertFalse(gs.whiteCanCastleKing)
        self.assertFalse(gs.whiteCanCastleQueen)

    def test_white_queenside_moves_rook(self):
        gs = ChessEngine.GameState()
        for san in ["d4", "d5", "Nc3", "Nc6", "Bf4", "Nf6", "Qd2", "e6"]:
            matches = [m for m in gs.getValidMoves() if move_matches_san(m, san)]
            self.assertEqual(len(matches), 1, san)
            gs.makeMove(matches[0])
        matches = [m for m in gs.getValidMoves() if move_matches_san(m, "O-O-O")]
        self.assertEqual(len(matches), 1)
        gs.makeMove(matches[0])
        self.assertEqual(gs.board[7][2], "wK")
        self.assertEqual(gs.board[7][3], "wR")
        self.assertEqual(gs.board[7][0], ChessEngine.BLANK_SPACE)

    def test_cannot_castle_through_check(self):
        gs = ChessEngine.GameState()
        gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
        gs.board[7][4] = "wK"
        gs.board[7][7] = "wR"
        gs.board[0][4] = "bK"
        gs.board[0][5] = "bR"  # attacks f1
        gs.whiteToMove = True
        gs.whiteCanCastleKing = True
        gs.whiteCanCastleQueen = False
        gs.blackCanCastleKing = False
        gs.blackCanCastleQueen = False
        legal = [m.getChessNotation() for m in gs.getValidMoves() if m.castle]
        self.assertEqual(legal, [])

    def test_undo_castling(self):
        gs = ChessEngine.GameState()
        for san in ["e4", "e5", "Nf3", "Nc6", "Be2", "Nf6", "O-O"]:
            matches = [m for m in gs.getValidMoves() if move_matches_san(m, san)]
            self.assertEqual(len(matches), 1, san)
            gs.makeMove(matches[0])
        gs.undoMove()
        self.assertEqual(gs.board[7][4], "wK")
        self.assertEqual(gs.board[7][7], "wR")
        self.assertTrue(gs.whiteCanCastleKing)


class PromotionTests(unittest.TestCase):
    def test_white_promotes_to_each_piece(self):
        for piece in "QRBN":
            gs = ChessEngine.GameState()
            gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
            gs.board[1][0] = "wp"  # a7
            gs.board[7][4] = "wK"
            gs.board[0][4] = "bK"
            gs.whiteToMove = True
            gs.whiteCanCastleKing = gs.whiteCanCastleQueen = False
            gs.blackCanCastleKing = gs.blackCanCastleQueen = False
            legal = [m for m in gs.getValidMoves() if m.pawnPromotion]
            chosen = [m for m in legal if m.promotionPiece == "w" + piece]
            self.assertEqual(len(chosen), 1, piece)
            gs.makeMove(chosen[0])
            self.assertEqual(gs.board[0][0], "w" + piece)
            gs.undoMove()
            self.assertEqual(gs.board[1][0], "wp")

    def test_capture_promotion(self):
        gs = ChessEngine.GameState()
        gs.board = [[ChessEngine.BLANK_SPACE] * 8 for _ in range(8)]
        gs.board[1][0] = "wp"
        gs.board[0][1] = "bR"
        gs.board[7][4] = "wK"
        gs.board[0][4] = "bK"
        gs.whiteToMove = True
        gs.whiteCanCastleKing = gs.whiteCanCastleQueen = False
        gs.blackCanCastleKing = gs.blackCanCastleQueen = False
        queen_cap = [m for m in gs.getValidMoves()
                     if m.pawnPromotion and m.endCol == 1 and m.promotionPiece == "wQ"]
        self.assertEqual(len(queen_cap), 1)
        gs.makeMove(queen_cap[0])
        self.assertEqual(gs.board[0][1], "wQ")
        self.assertFalse(gs.blackCanCastleKing)  # rook captured on h8? wait b1 is file b rank 8 = (0,1) not a rook corner
        # b8 rook capture shouldn't change a8/h8 rights; rights already false


class DocumentedGameTests(unittest.TestCase):
    """Games published on chessgames.com / Wikipedia so the replay can be checked independently."""

    def test_gundersen_faul_1928_enpassant_mate(self):
        # https://www.chessgames.com/perl/chessgame?gid=1242924
        # 15. hxg6 is checkmate by en passant
        movetext = """
        1. e4 e6 2. d4 d5 3. e5 c5 4. c3 cxd4 5. cxd4 Bb4+ 6. Nc3 Nc6
        7. Nf3 Nge7 8. Bd3 O-O 9. Bxh7+ Kxh7 10. Ng5+ Kg6 11. h4 Nxd4
        12. Qg4 f5 13. h5+ Kh6 14. Nxe6+ g5 15. hxg6#
        """
        gs, played = play_pgn(movetext)
        self.assertTrue(played[-1].enpassant)
        self.assertEqual(played[-1].getChessNotation(), "h5g6")
        self.assertEqual(gs.board[2][6], "wp")  # g6
        self.assertEqual(gs.board[3][6], ChessEngine.BLANK_SPACE)  # g5 pawn removed
        self.assertEqual(len(gs.getValidMoves()), 0)  # checkmate
        self.assertTrue(any(m.castle for m in played))

    def test_capablanca_tartakower_new_york_1924_fifty_moves_castling(self):
        # Capablanca vs Tartakower, New York 1924 (published widely, e.g. chessgames.com).
        # Famous rook ending; both sides castle. 52 moves.
        movetext = """
        1. d4 e6 2. Nf3 f5 3. c4 Nf6 4. Bg5 Be7 5. Nc3 O-O 6. e3 b6
        7. Bd3 Bb7 8. O-O Qe8 9. Qe2 Ne4 10. Bxe7 Nxc3 11. bxc3 Qxe7
        12. a4 Bxf3 13. Qxf3 Nc6 14. Rfb1 Rae8 15. Qh3 Rf6 16. f4 Na5
        17. Qf3 d6 18. Re1 Qd7 19. e4 fxe4 20. Qxe4 g6 21. g3 Kf8
        22. Kg2 Rf7 23. h4 d5 24. cxd5 exd5 25. Qxe8+ Qxe8 26. Rxe8+ Kxe8
        27. h5 Rf6 28. hxg6 hxg6 29. Rh1 Kf8 30. Rh7 Rc6 31. g4 Nc4
        32. g5 Ne3+ 33. Kf3 Nf5 34. Bxf5 gxf5 35. Kg3 Rxc3+ 36. Kh4 Rf3
        37. g6 Rxf4+ 38. Kg5 Re4 39. Kf6 Kg8 40. Rg7+ Kh8 41. Rxc7 Re8
        42. Kxf5 Re4 43. Kf6 Rf4+ 44. Ke5 Rg4 45. g7+ Kg8 46. Rxa7 Rg1
        47. Kxd5 Rc1 48. Kd6 Rc2 49. d5 Rc1 50. Rc7 Ra1 51. Kc6 Rxa4 52. d6
        """
        gs, played = play_pgn(movetext)
        self.assertEqual(len(played), 103)  # 52 full moves minus black's 52nd
        self.assertTrue(any(m.castle for m in played))
        self.assertEqual(gs.board[2][3], "wp")  # d6 after 52. d6

    def test_kasparov_topalov_1999_queenside_castling(self):
        # Kasparov vs Topalov, Wijk aan Zee 1999 (both sides O-O-O)
        movetext = """
        1. e4 d6 2. d4 Nf6 3. Nc3 g6 4. Be3 Bg7 5. Qd2 c6 6. f3 b5
        7. Nge2 Nbd7 8. Bh6 Bxh6 9. Qxh6 Bb7 10. a3 e5 11. O-O-O Qe7
        12. Kb1 a6 13. Nc1 O-O-O 14. Nb3 exd4 15. Rxd4 c5 16. Rd1 Nb6
        17. g3 Kb8 18. Na5 Ba8 19. Bh3 d5 20. Qf4+ Ka7 21. Rhe1 d4
        22. Nd5 Nbxd5 23. exd5 Qd6 24. Rxd4 cxd4 25. Re7+ Kb6
        26. Qxd4+ Kxa5 27. b4+ Ka4 28. Qc3 Qxd5 29. Ra7 Bb7 30. Rxb7 Qc4
        31. Qxf6 Kxa3 32. Qxa6+ Kxb4 33. c3+ Kxc3 34. Qa1+ Kd2
        35. Qb2+ Kd1 36. Bf1 Rd2 37. Rd7 Rxd7 38. Bxc4 bxc4 39. Qxh8 Rd3
        40. Qa8 c3 41. Qa4+ Ke1 42. f4 f5 43. Kc1 Rd2 44. Qa7
        """
        gs, played = play_pgn(movetext)
        castles = [m for m in played if m.castle]
        self.assertEqual(len(castles), 2)
        self.assertEqual(castles[0].endCol, 2)
        self.assertEqual(castles[1].endCol, 2)


if __name__ == "__main__":
    unittest.main()
