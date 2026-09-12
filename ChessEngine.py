"""
This class is responsible for storing information about the current state of a chess game.
Also responsible for determining the valid moves at the current state. It will also keep a move log.
"""


BLANK_SPACE = "--"
PROMOTION_PIECES = ("Q", "R", "B", "N")


class GameState():
    def __init__(self):
        self.board = [
            ["bR", "bN", "bB", "bQ", "bK", "bB", "bN", "bR"],
            ["bp", "bp", "bp", "bp", "bp", "bp", "bp", "bp"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["--", "--", "--", "--", "--", "--", "--", "--"],
            ["wp", "wp", "wp", "wp", "wp", "wp", "wp", "wp"],
            ["wR", "wN", "wB", "wQ", "wK", "wB", "wN", "wR"]]

        self.whiteToMove = True
        self.blackCanCastleKing = True
        self.blackCanCastleQueen = True
        self.whiteCanCastleKing = True
        self.whiteCanCastleQueen = True
        self.moveLog = []

    def makeMove(self, move):
        self._inferSpecialMoveFlags(move)

        move.castleRights = (
            self.whiteCanCastleKing,
            self.whiteCanCastleQueen,
            self.blackCanCastleKing,
            self.blackCanCastleQueen,
        )

        self.board[move.startRow][move.startCol] = BLANK_SPACE
        self.board[move.endRow][move.endCol] = move.pieceMoved

        # Removes pawn that was captured en passant (the pawn is not on the destination square)
        if move.enpassant:
            self.board[move.startRow][move.endCol] = BLANK_SPACE

        if move.castle:
            if move.endCol == 6:  # kingside: rook h-file -> f-file
                self.board[move.endRow][5] = self.board[move.endRow][7]
                self.board[move.endRow][7] = BLANK_SPACE
            elif move.endCol == 2:  # queenside: rook a-file -> d-file
                self.board[move.endRow][3] = self.board[move.endRow][0]
                self.board[move.endRow][0] = BLANK_SPACE

        if move.pawnPromotion:
            if move.promotionPiece is None:
                move.promotionPiece = move.pieceMoved[0] + "Q"
            self.board[move.endRow][move.endCol] = move.promotionPiece

        self._updateCastleRights(move)

        self.moveLog.append(move)  # log move
        self.whiteToMove = not self.whiteToMove  # next turn

    def _inferSpecialMoveFlags(self, move):
        """Fill in en passant / castle / promotion when the UI built a move from clicks only."""
        if move.pieceMoved[1] == "p" and move.startCol != move.endCol and move.pieceCaptured == BLANK_SPACE:
            move.enpassant = True
            move.pieceCaptured = "bp" if move.pieceMoved[0] == "w" else "wp"

        if move.pieceMoved[1] == "K" and abs(move.endCol - move.startCol) == 2:
            move.castle = True

        if move.pieceMoved[1] == "p" and move.endRow in (0, 7):
            move.pawnPromotion = True
            if move.promotionPiece is None:
                move.promotionPiece = move.pieceMoved[0] + "Q"

    def _updateCastleRights(self, move):
        if move.pieceMoved == "wK":
            self.whiteCanCastleKing = False
            self.whiteCanCastleQueen = False
        elif move.pieceMoved == "bK":
            self.blackCanCastleKing = False
            self.blackCanCastleQueen = False

        if move.pieceMoved == "wR":
            if move.startRow == 7 and move.startCol == 7:
                self.whiteCanCastleKing = False
            if move.startRow == 7 and move.startCol == 0:
                self.whiteCanCastleQueen = False
        elif move.pieceMoved == "bR":
            if move.startRow == 0 and move.startCol == 7:
                self.blackCanCastleKing = False
            if move.startRow == 0 and move.startCol == 0:
                self.blackCanCastleQueen = False

        if move.pieceCaptured == "wR":
            if move.endRow == 7 and move.endCol == 7:
                self.whiteCanCastleKing = False
            if move.endRow == 7 and move.endCol == 0:
                self.whiteCanCastleQueen = False
        elif move.pieceCaptured == "bR":
            if move.endRow == 0 and move.endCol == 7:
                self.blackCanCastleKing = False
            if move.endRow == 0 and move.endCol == 0:
                self.blackCanCastleQueen = False

    def undoMove(self):
        if len(self.moveLog) == 0:
            return

        move = self.moveLog.pop()
        self.whiteToMove = not self.whiteToMove

        if move.castleRights is not None:
            (self.whiteCanCastleKing,
             self.whiteCanCastleQueen,
             self.blackCanCastleKing,
             self.blackCanCastleQueen) = move.castleRights

        if move.enpassant:
            self.board[move.endRow][move.endCol] = BLANK_SPACE
            self.board[move.startRow][move.endCol] = move.pieceCaptured
            self.board[move.startRow][move.startCol] = move.pieceMoved
        elif move.castle:
            self.board[move.endRow][move.endCol] = BLANK_SPACE
            self.board[move.startRow][move.startCol] = move.pieceMoved
            if move.endCol == 6:  # kingside
                self.board[move.endRow][7] = self.board[move.endRow][5]
                self.board[move.endRow][5] = BLANK_SPACE
            else:  # queenside
                self.board[move.endRow][0] = self.board[move.endRow][3]
                self.board[move.endRow][3] = BLANK_SPACE
        else:
            self.board[move.endRow][move.endCol] = move.pieceCaptured
            self.board[move.startRow][move.startCol] = move.pieceMoved

    """
    gets valid moves considering checks
    """

    def getValidMoves(self):
        validMoves = []
        possibleMoves = self.getAllPossibleMoves(validate=True)

        for x in possibleMoves:
            self.makeMove(x)
            responses = self.getAllPossibleMoves(validate=True)

            valid = True
            for i in responses:
                if i.pieceCaptured[1] == "K":
                    valid = False
                    break

            if valid:
                validMoves.append(x)

            self.undoMove()

        return validMoves

    """
    gets moves, not considering checks

    validate is to keep console logs clean of validation checks
    """

    def getAllPossibleMoves(self, validate=False, includeCastle=True):
        moves = []

        for row in range(len(self.board)):
            for col in range(len(self.board[row])):
                turn = self.board[row][col][0]
                if (turn == "w" and self.whiteToMove) or (turn == "b" and not self.whiteToMove):
                    piece = self.board[row][col][1]
                    if piece == "p":
                        self.getPawnMoves(row, col, moves)
                    if piece == "N":
                        self.getKnightMoves(row, col, moves)
                    if piece == "B":
                        self.getBishopMoves(row, col, moves)
                    if piece == "R":
                        self.getRookMoves(row, col, moves)
                    if piece == "Q":
                        self.getQueenMoves(row, col, moves)
                    if piece == "K":
                        self.getKingMoves(row, col, moves, includeCastle=includeCastle)

        if len(self.moveLog) != 0 and self.moveLog[-1].pieceMoved[1] == "p" and (
                self.moveLog[-1].startRow - self.moveLog[-1].endRow) in (-2, 2):
            self.enpeasant(moves, validate=validate)

        return moves

    def _addPawnMove(self, start, end, moves, enpassant=False):
        if enpassant:
            moves.append(Move(start, end, self.board, enpassant=True))
            return
        endRow = end[0]
        if endRow == 0 or endRow == 7:
            color = self.board[start[0]][start[1]][0]
            for pieceType in PROMOTION_PIECES:
                moves.append(Move(start, end, self.board, pawnPromotion=True,
                                  promotionPiece=color + pieceType))
        else:
            moves.append(Move(start, end, self.board, enpassant=enpassant))

    """Get pawn moves for pawn located at position and add moves to list"""

    def getPawnMoves(self, row, col, moves):
        if self.whiteToMove:
            # non capture movement
            if row - 1 >= 0 and self.board[row - 1][col] == "--":
                self._addPawnMove((row, col), (row - 1, col), moves)
                if row == 6 and self.board[row - 2][col] == "--":
                    self._addPawnMove((row, col), (row - 2, col), moves)
            # captures
            if row - 1 >= 0 and col - 1 >= 0 and self.board[row - 1][col - 1][0] == "b":
                self._addPawnMove((row, col), (row - 1, col - 1), moves)
            if row - 1 >= 0 and col + 1 < 8 and self.board[row - 1][col + 1][0] == "b":
                self._addPawnMove((row, col), (row - 1, col + 1), moves)

        else:
            # non capture movement
            if row + 1 < 8 and self.board[row + 1][col] == "--":
                self._addPawnMove((row, col), (row + 1, col), moves)
                if row == 1 and self.board[row + 2][col] == "--":
                    self._addPawnMove((row, col), (row + 2, col), moves)

            # captures
            if row + 1 < 8 and col - 1 >= 0 and self.board[row + 1][col - 1][0] == "w":
                self._addPawnMove((row, col), (row + 1, col - 1), moves)
            if row + 1 < 8 and col + 1 < 8 and self.board[row + 1][col + 1][0] == "w":
                self._addPawnMove((row, col), (row + 1, col + 1), moves)

    """Gets possible en passant moves"""

    def enpeasant(self, moves, validate=False):
        pawnMoved = (self.moveLog[-1].endRow, self.moveLog[-1].endCol)
        if self.whiteToMove:
            dest = (pawnMoved[0] - 1, pawnMoved[1])
            # pawn to left
            if pawnMoved[1] - 1 >= 0 and self.board[pawnMoved[0]][pawnMoved[1] - 1] == "wp":
                self._addPawnMove((pawnMoved[0], pawnMoved[1] - 1), dest, moves, enpassant=True)
                if not validate:
                    print("Enpeasant to left")

            # pawn to right
            if pawnMoved[1] + 1 < 8 and self.board[pawnMoved[0]][pawnMoved[1] + 1] == "wp":
                self._addPawnMove((pawnMoved[0], pawnMoved[1] + 1), dest, moves, enpassant=True)
                if not validate:
                    print("Enpeasant to right")

        else:
            dest = (pawnMoved[0] + 1, pawnMoved[1])
            # pawn to left
            if pawnMoved[1] - 1 >= 0 and self.board[pawnMoved[0]][pawnMoved[1] - 1] == "bp":
                self._addPawnMove((pawnMoved[0], pawnMoved[1] - 1), dest, moves, enpassant=True)
                if not validate:
                    print("Enpeasant to left")

            # pawn to right
            if pawnMoved[1] + 1 < 8 and self.board[pawnMoved[0]][pawnMoved[1] + 1] == "bp":
                self._addPawnMove((pawnMoved[0], pawnMoved[1] + 1), dest, moves, enpassant=True)
                if not validate:
                    print("Enpeasant to right")

    """Get moves for knight located at position and add moves to list"""

    def getKnightMoves(self, row, col, moves):
        if row - 2 >= 0 and col - 1 >= 0 and (self.board[row - 2][col - 1][0] == "-" or self.board[row - 2][col - 1][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row - 2, col - 1), self.board))

        if row - 2 >= 0 and col + 1 < 8 and (self.board[row - 2][col + 1][0] == "-" or self.board[row - 2][col + 1][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row - 2, col + 1), self.board))

        if row + 2 < 8 and col - 1 >= 0 and (self.board[row + 2][col - 1][0] == "-" or self.board[row + 2][col - 1][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row + 2, col - 1), self.board))

        if row + 2 < 8 and col + 1 < 8 and (self.board[row + 2][col + 1][0] == "-" or self.board[row + 2][col + 1][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row + 2, col + 1), self.board))

        if row - 1 >= 0 and col - 2 >= 0 and (self.board[row - 1][col - 2][0] == "-" or self.board[row - 1][col - 2][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row - 1, col - 2), self.board))

        if row - 1 >= 0 and col + 2 < 8 and (self.board[row - 1][col + 2][0] == "-" or self.board[row - 1][col + 2][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row - 1, col + 2), self.board))

        if row + 1 < 8 and col - 2 >= 0 and (self.board[row + 1][col - 2][0] == "-" or self.board[row + 1][col - 2][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row + 1, col - 2), self.board))

        if row + 1 < 8 and col + 2 < 8 and (self.board[row + 1][col + 2][0] == "-" or self.board[row + 1][col + 2][
            0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (row + 1, col + 2), self.board))

    """Get moves for bishop located at position and add moves to list"""

    def getBishopMoves(self, row, col, moves):
        r = row + 1
        c = col + 1
        while r < 8 and c < 8 and self.board[r][c] == "--":
            moves.append(Move((row, col), (r, c), self.board))
            r += 1
            c += 1

        if r < 8 and c < 8 and self.board[r][c][0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove):
            moves.append(Move((row, col), (r, c), self.board))

        r = row + 1
        c = col - 1
        while r < 8 and c >= 0 and self.board[r][c] == "--":
            moves.append(Move((row, col), (r, c), self.board))
            r += 1
            c -= 1

        if r < 8 and c >= 0 and self.board[r][c][0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove):
            moves.append(Move((row, col), (r, c), self.board))

        r = row - 1
        c = col + 1
        while r >= 0 and c < 8 and self.board[r][c] == "--":
            moves.append(Move((row, col), (r, c), self.board))
            r -= 1
            c += 1

        if r >= 0 and c < 8 and self.board[r][c][0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove):
            moves.append(Move((row, col), (r, c), self.board))

        r = row - 1
        c = col - 1
        while r >= 0 and c >= 0 and self.board[r][c] == "--":
            moves.append(Move((row, col), (r, c), self.board))
            r -= 1
            c -= 1

        if r >= 0 and c >= 0 and self.board[r][c][0] == "b" * self.whiteToMove + "w" * (not self.whiteToMove):
            moves.append(Move((row, col), (r, c), self.board))

    """Get moves for rook located at position and add moves to list"""

    def getRookMoves(self, row, col, moves):
        r = row
        c = col + 1
        while c < 8 and self.board[r][c] == BLANK_SPACE:
            moves.append(Move((row, col), (r, c), self.board))
            c += 1

        if c < 8 and self.board[r][c][0] == ("b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (r, c), self.board))

        r = row
        c = col - 1
        while c >= 0 and self.board[r][c] == BLANK_SPACE:
            moves.append(Move((row, col), (r, c), self.board))
            c -= 1

        if c >= 0 and self.board[r][c][0] == ("b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (r, c), self.board))

        r = row + 1
        c = col
        while r < 8 and self.board[r][c] == BLANK_SPACE:
            moves.append(Move((row, col), (r, c), self.board))
            r += 1

        if r < 8 and self.board[r][c][0] == ("b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (r, c), self.board))

        r = row - 1
        c = col
        while r >= 0 and self.board[r][c] == BLANK_SPACE:
            moves.append(Move((row, col), (r, c), self.board))
            r -= 1

        if r >= 0 and self.board[r][c][0] == ("b" * self.whiteToMove + "w" * (not self.whiteToMove)):
            moves.append(Move((row, col), (r, c), self.board))

    """Get moves for queen located at position and add moves to list"""

    def getQueenMoves(self, row, col, moves):
        self.getRookMoves(row, col, moves)
        self.getBishopMoves(row, col, moves)

    """Get moves for king located at position and add moves to list"""

    def getKingMoves(self, row, col, moves, includeCastle=True):
        aroundKing = (
        (row + 1, col + 1), (row + 1, col), (row, col + 1), (row + 1, col - 1), (row - 1, col + 1), (row - 1, col),
        (row, col - 1), (row - 1, col - 1))

        for square in aroundKing:
            try:
                if square[0] >= 0 and square[1] >= 0 and self.board[square[0]][square[1]][0] != (
                        "w" * self.whiteToMove + "b" * (not self.whiteToMove)):
                    moves.append(Move((row, col), square, self.board))
            except IndexError:
                pass

        if includeCastle:
            if self.whiteToMove:
                self.castleWhiteChecker(moves)
            else:
                self.castleBlackChecker(moves)

    def squareUnderAttack(self, row, col):
        """True if the side to move's opponent attacks (row, col)."""
        self.whiteToMove = not self.whiteToMove
        opponentMoves = self.getAllPossibleMoves(validate=True, includeCastle=False)
        self.whiteToMove = not self.whiteToMove
        for move in opponentMoves:
            if move.endRow == row and move.endCol == col:
                return True
        return False

    """These two functions see if the king can castle for their respective color
    Doesn't check if king can be taken after because that is handled in valid moves, just if the other squares are under attack"""

    def castleWhiteChecker(self, moves):
        if self.board[7][4] != "wK":
            return
        if self.squareUnderAttack(7, 4):
            return

        if self.whiteCanCastleKing and self.board[7][5] == BLANK_SPACE and self.board[7][6] == BLANK_SPACE and \
                self.board[7][7] == "wR" and not self.squareUnderAttack(7, 5):
            moves.append(Move((7, 4), (7, 6), self.board, castle=True))

        if self.whiteCanCastleQueen and self.board[7][1] == BLANK_SPACE and self.board[7][2] == BLANK_SPACE and \
                self.board[7][3] == BLANK_SPACE and self.board[7][0] == "wR" and not self.squareUnderAttack(7, 3):
            moves.append(Move((7, 4), (7, 2), self.board, castle=True))

    def castleBlackChecker(self, moves):
        if self.board[0][4] != "bK":
            return
        if self.squareUnderAttack(0, 4):
            return

        if self.blackCanCastleKing and self.board[0][5] == BLANK_SPACE and self.board[0][6] == BLANK_SPACE and \
                self.board[0][7] == "bR" and not self.squareUnderAttack(0, 5):
            moves.append(Move((0, 4), (0, 6), self.board, castle=True))

        if self.blackCanCastleQueen and self.board[0][1] == BLANK_SPACE and self.board[0][2] == BLANK_SPACE and \
                self.board[0][3] == BLANK_SPACE and self.board[0][0] == "bR" and not self.squareUnderAttack(0, 3):
            moves.append(Move((0, 4), (0, 2), self.board, castle=True))


class Move():
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}

    def __init__(self, startSquare, endSquare, board, enpassant=False, pawnPromotion=False, castle=False,
                 promotionPiece=None):
        self.enpassant = enpassant
        self.pawnPromotion = pawnPromotion
        self.castle = castle
        self.promotionPiece = promotionPiece
        self.castleRights = None

        self.startRow = startSquare[0]
        self.startCol = startSquare[1]

        self.endRow = endSquare[0]
        self.endCol = endSquare[1]

        self.pieceMoved = board[self.startRow][self.startCol]

        if enpassant:
            self.pieceCaptured = "wp" if self.pieceMoved == "bp" else "bp"
        else:
            self.pieceCaptured = board[self.endRow][self.endCol]

        if pawnPromotion and self.promotionPiece is None and self.pieceMoved[0] in ("w", "b"):
            self.promotionPiece = self.pieceMoved[0] + "Q"

        # basically a hash function
        self.moveID = self.startRow * 1000 + self.startCol * 100 + self.endRow * 10 + self.endCol

    """
    Overiding equals operator

    Dependent that the moves are in the same board state
    """

    def __eq__(self, other):
        if isinstance(other, Move):
            return self.moveID == other.moveID
        return False

    def getRankFile(self, row, col):
        return self.colsToFiles[col] + self.rowsToRanks[row]

    def getChessNotation(self):
        notation = self.getRankFile(self.startRow, self.startCol) + self.getRankFile(self.endRow, self.endCol)
        if self.pawnPromotion and self.promotionPiece:
            notation += self.promotionPiece[1].lower()
        return notation
