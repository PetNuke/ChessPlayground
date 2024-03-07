"""
This class is responsible for storing information about the current state of a chess game.
Also responsible for determining the valid moves at the current state. It will also keep a move log.
"""


BLANK_SPACE = "--"


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
        self.board[move.startRow][move.startCol] = BLANK_SPACE
        self.board[move.endRow][move.endCol] = move.pieceMoved

        # Removes pawn that was captured
        if move.enpassant:
            assert move.startRow != move.endRow
            assert move.startCol != move.endCol

            print("makeMove: removing the captured pawn")
            self.board[move.startRow][move.endCol] = BLANK_SPACE # TODO this line is not working


        # Castling rights adjustment -- This code is very messy should look for alternatives
        if move.pieceMoved[1] == 'K':
            if self.whiteToMove:
                self.whiteCanCastleQueen = False
                self.whiteCanCastleKing = False
            else:
                self.blackCanCastleKing = False
                self.blackCanCastleQueen = False

        if move.pieceMoved[1] == 'R':
            if self.whiteToMove:
                if self.whiteCanCastleKing and move.startRow == 7 and move.startCol == 7:
                    self.whiteCanCastleKing = False
                if self.whiteCanCastleQueen and move.startRow == 7 and move.startCol == 0:
                    self.whiteCanCastleQueen = False
            else:
                if self.blackCanCastleKing and move.startRow == 0 and move.startCol == 7:
                    self.blackCanCastleKing = False
                if self.blackCanCastleQueen and move.startRow == 0 and move.startCol == 0:
                    self.blackCanCastleQueen = False

        if move.pieceCaptured[1] == 'R':
            if self.whiteToMove:
                if self.whiteCanCastleKing and move.endRow == 7 and move.endCol == 7:
                    self.whiteCanCastleKing = False
                if self.whiteCanCastleQueen and move.endRow == 7 and move.endCol == 0:
                    self.whiteCanCastleQueen = False
            else:
                if self.blackCanCastleKing and move.endRow == 0 and move.endCol == 7:
                    self.blackCanCastleKing = False
                if self.blackCanCastleQueen and move.endRow == 0 and move.endCol == 0:
                    self.blackCanCastleQueen = False

        self.moveLog.append(move)  # log move
        self.whiteToMove = not self.whiteToMove  # next turn

    def undoMove(self):
        if len(self.moveLog) == 0:
            return

        move = self.moveLog[-1]

        if move.enpassant:
            self.board[move.endRow][move.endCol] = BLANK_SPACE
            self.board[move.startRow][move.endCol] = move.pieceCaptured
            self.board[move.startRow][move.startCol] = move.pieceMoved
            self.whiteToMove = not self.whiteToMove

        else:
            self.board[move.endRow][move.endCol] = move.pieceCaptured
            self.board[move.startRow][move.startCol] = move.pieceMoved
            self.whiteToMove = not self.whiteToMove

        self.moveLog.pop()

    """
    gets valid moves considering checks
    """

    def getValidMoves(self):
        validMoves = []
        possibleMoves = self.getAllPossibleMoves()

        for x in possibleMoves:
            self.makeMove(x)
            responses = self.getAllPossibleMoves(validate=True)

            valid = True
            for i in responses:
                # print(i.getChessNotation())
                if i.pieceCaptured[1] == 'K':
                    valid = False

            if valid:
                # print("Adding", x.getChessNotation())
                validMoves.append(x)
            else:
                # print("Rejected", x.getChessNotation())
                pass

            self.undoMove()

        validMoves.append(9)
        return validMoves

    """
    gets moves, not considering checks
    
    validate is to keep console logs clean of validation checks
    """

    def getAllPossibleMoves(self, validate=False):
        moves = []

        for row in range(len(self.board)):
            for col in range(len(self.board[row])):
                turn = self.board[row][col][0]
                if (turn == 'w' and self.whiteToMove) or (turn == 'b' and not self.whiteToMove):
                    piece = self.board[row][col][1]
                    if piece == 'p':
                        self.getPawnMoves(row, col, moves)
                    if piece == 'N':
                        self.getKnightMoves(row, col, moves)
                    if piece == 'B':
                        self.getBishopMoves(row, col, moves)
                    if piece == 'R':
                        self.getRookMoves(row, col, moves)
                    if piece == 'Q':
                        self.getQueenMoves(row, col, moves)
                    if piece == 'K':
                        self.getKingMoves(row, col, moves)

        if len(self.moveLog) != 0 and self.moveLog[-1].pieceMoved[1] == 'p' and (
                self.moveLog[-1].startRow - self.moveLog[-1].endRow) in (-2, 2):
            self.enpeasant(moves, validate=validate)
            if not validate:
                print("Searching for enpeasant")
        else:
            if not validate:
                print("No enpeasant")

        return moves

    """Get pawn moves for pawn located at position and add moves to list"""

    # TODO and promotions

    def getPawnMoves(self, row, col, moves):
        if self.whiteToMove:
            # non capture movement
            if self.board[row - 1][col] == "--":
                moves.append(Move((row, col), (row - 1, col), self.board))
                if row == 6 and self.board[row - 2][col] == "--":
                    moves.append(Move((row, col), (row - 2, col), self.board))
            # captures
            if col - 1 >= 0 and self.board[row - 1][col - 1][0] == "b":
                moves.append(Move((row, col), (row - 1, col - 1), self.board))
            if col + 1 < 8 and self.board[row - 1][col + 1][0] == "b":
                moves.append(Move((row, col), (row - 1, col + 1), self.board))

        else:
            # non capture movement
            if self.board[row + 1][col] == "--":
                moves.append(Move((row, col), (row + 1, col), self.board))
                if row == 1 and self.board[row + 2][col] == "--":
                    moves.append(Move((row, col), (row + 2, col), self.board))

            # captures
            if col - 1 >= 0 and self.board[row + 1][col - 1][0] == "w":
                moves.append(Move((row, col), (row + 1, col - 1), self.board))
            if col + 1 < 8 and self.board[row + 1][col + 1][0] == "w":
                moves.append(Move((row, col), (row + 1, col + 1), self.board))

    # TODO
    """Gets possible enpeasant moves"""

    def enpeasant(self, moves, validate=False):
        pawnMoved = (self.moveLog[-1].endRow, self.moveLog[-1].endCol)
        if self.whiteToMove:
            # pawn to left
            if pawnMoved[1] - 1 >= 0 and self.board[pawnMoved[0]][pawnMoved[1] - 1] == 'wp':
                moves.append(Move((pawnMoved[0], pawnMoved[1] - 1), (pawnMoved[0] - 1, pawnMoved[1]), self.board,
                                  enpassant=True))

                if not validate:
                    print("Enpeasant to left")

            # pawn to right
            if pawnMoved[1] + 1 < 8 and self.board[pawnMoved[0]][pawnMoved[1] + 1] == 'wp':
                moves.append(Move((pawnMoved[0], pawnMoved[1] + 1), (pawnMoved[0] - 1, pawnMoved[1]), self.board,
                                  enpassant=True))

                if not validate:
                    print("Enpeasant to right")

        else:
            # pawn to left
            if pawnMoved[1] - 1 >= 0 and self.board[pawnMoved[0]][pawnMoved[1] - 1] == 'bp':
                moves.append(Move((pawnMoved[0], pawnMoved[1] - 1), (pawnMoved[0] + 1, pawnMoved[1]), self.board,
                                  enpassant=True))

                if not validate:
                    print("Enpeasant to left")

            # pawn to right
            if pawnMoved[1] + 1 < 8 and self.board[pawnMoved[0]][pawnMoved[1] + 1] == 'bp':
                moves.append(Move((pawnMoved[0], pawnMoved[1] + 1), (pawnMoved[0] + 1, pawnMoved[1]), self.board,
                                  enpassant=True))

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

    # TODO castling

    def getKingMoves(self, row, col, moves):
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

        if self.whiteToMove:
            self.castleWhiteChecker(moves)
        else:
            self.castleBlackChecker(moves)

    """These two functions see if the king can castle for their respective color
    Doesn't check if king can be taken after because that is handled in valid moves, just if the other squares are under attack"""

    def castleWhiteChecker(self, moves):
        pass

    def castleBlackChecker(self, moves):
        pass


class Move():
    ranksToRows = {"1": 7, "2": 6, "3": 5, "4": 4, "5": 3, "6": 2, "7": 1, "8": 0}
    rowsToRanks = {v: k for k, v in ranksToRows.items()}
    filesToCols = {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4, "f": 5, "g": 6, "h": 7}
    colsToFiles = {v: k for k, v in filesToCols.items()}

    def __init__(self, startSquare, endSquare, board, enpassant=False, pawnPromotion=False, castle=False):
        self.enpassant = enpassant
        self.pawnPromotion = pawnPromotion
        self.castle = castle

        self.startRow = startSquare[0]
        self.startCol = startSquare[1]

        self.endRow = endSquare[0]
        self.endCol = endSquare[1]

        self.pieceMoved = board[self.startRow][self.startCol]

        if enpassant:
            self.pieceCaptured = "wp" if self.pieceMoved == "bp" else "bp"
        else:
            self.pieceCaptured = board[self.endRow][self.endCol]

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

    # TODO update this to get full chess notation
    def getChessNotation(self):
        return self.getRankFile(self.startRow, self.startCol) + self.getRankFile(self.endRow, self.endCol)
