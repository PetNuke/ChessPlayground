# Handles user input and displaying current game state

import pygame as p
import ChessEngine

width = height = 512
dimension = 8

squareSize = height // dimension

maxFPS = 15  # for animations
IMAGES = {}

PROMOTION_ORDER = ["Q", "R", "B", "N"]


"""
Initialize a global dictionary of images. Called once
"""
def loadImages():
    pieces = ["wp", "wR", "wN", "wB", "wK", "wQ", "bp", "bR", "bN", "bB", "bK", "bQ"]

    for x in pieces:
        IMAGES[x] = p.transform.scale(p.image.load("images/" + x + ".png"), (squareSize, squareSize))


def matchingValidMoves(clickMove, validMoves):
    return [m for m in validMoves if isinstance(m, ChessEngine.Move) and m == clickMove]


"""
main driver for code. Handles user input and updating the graphics
"""
def main():
    p.init()
    screen = p.display.set_mode((width, height))
    clock = p.time.Clock()
    screen.fill(p.Color("white"))
    gs = ChessEngine.GameState()
    validMoves = gs.getValidMoves()
    if validMoves:
        print(validMoves[0])
    moveMade = False

    loadImages()
    running = True
    squareSelected = ()
    playerClicks = []
    pendingPromotion = []  # legal promotion moves for the chosen from/to squares

    print("Game Start")

    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                running = False

            # mouse handler
            elif e.type == p.MOUSEBUTTONDOWN:  # could add functionality to drag and drop
                location = p.mouse.get_pos()  # col, row
                col = location[0] // squareSize
                row = location[1] // squareSize

                if pendingPromotion:
                    chosen = promotionChoiceFromClick(row, col, pendingPromotion)
                    if chosen is not None:
                        gs.makeMove(chosen)
                        moveMade = True
                    pendingPromotion = []
                    squareSelected = ()
                    playerClicks = []
                    continue

                if squareSelected == (row, col):  # deselect
                    squareSelected = ()
                    playerClicks = []
                else:
                    squareSelected = (row, col)
                    playerClicks.append(squareSelected)
                if len(playerClicks) == 2:
                    move = ChessEngine.Move(playerClicks[0], playerClicks[1], gs.board)
                    matches = matchingValidMoves(move, validMoves)
                    if matches:
                        promoMatches = [m for m in matches if m.pawnPromotion]
                        if promoMatches:
                            pendingPromotion = promoMatches
                        else:
                            # Use the generated move so en passant / castle flags are set
                            gs.makeMove(matches[0])
                            moveMade = True

                    if not pendingPromotion:
                        squareSelected = ()
                        playerClicks = []

            # key handler
            elif e.type == p.KEYDOWN:
                if e.key == p.K_LEFT:
                    gs.undoMove()
                    pendingPromotion = []
                    moveMade = True
                elif pendingPromotion:
                    pieceKey = promotionPieceFromKey(e.key)
                    if pieceKey is not None:
                        for m in pendingPromotion:
                            if m.promotionPiece and m.promotionPiece[1] == pieceKey:
                                gs.makeMove(m)
                                moveMade = True
                                pendingPromotion = []
                                squareSelected = ()
                                playerClicks = []
                                break

        if moveMade:
            validMoves = gs.getValidMoves()
            moveMade = False

            if gs.whiteToMove:
                print("White's turn")
            else:
                print("Black's turn")

        clock.tick(maxFPS)
        p.display.flip()

        drawGameState(screen, gs, playerClicks, pendingPromotion)


def promotionPieceFromKey(key):
    if key == p.K_q:
        return "Q"
    if key == p.K_r:
        return "R"
    if key == p.K_b:
        return "B"
    if key == p.K_n:
        return "N"
    return None


def promotionChoiceFromClick(row, col, pendingPromotion):
    """Promotion choices are drawn on the destination rank, files a-d."""
    if not pendingPromotion:
        return None
    destRow = pendingPromotion[0].endRow
    if row != destRow or col > 3:
        return None
    pieceType = PROMOTION_ORDER[col]
    for m in pendingPromotion:
        if m.promotionPiece and m.promotionPiece[1] == pieceType:
            return m
    return None


"""
Responsible for graphics
"""
def drawGameState(screen, gs, playerClicks, pendingPromotion=None):
    drawBoard(screen, playerClicks)
    drawPieces(screen, gs.board)
    if pendingPromotion:
        drawPromotionPicker(screen, pendingPromotion)


# draws the squares of the board. Top left is always light square.
def drawBoard(screen, playerClicks):
    colors = [p.Color("white"), p.Color("gray")]
    for row in range(dimension):
        for col in range(dimension):
            color = colors[((row + col) % 2)]
            p.draw.rect(screen, color, p.Rect(col * squareSize, row * squareSize, squareSize, squareSize))

    if len(playerClicks) == 1:
        selectedSquare = playerClicks[0]
        color = colors[((selectedSquare[0] + selectedSquare[1]) % 2)]
        color = color.lerp(p.Color("red"), .1)
        p.draw.rect(screen, color, p.Rect(selectedSquare[1] * squareSize, selectedSquare[0] * squareSize, squareSize, squareSize))


def drawPieces(screen, board):
    for row in range(dimension):
        for col in range(dimension):
            piece = board[row][col]
            if piece != "--":
                screen.blit(IMAGES[piece], (col * squareSize, row * squareSize))


def drawPromotionPicker(screen, pendingPromotion):
    color = pendingPromotion[0].pieceMoved[0]
    destRow = pendingPromotion[0].endRow
    overlay = p.Surface((squareSize * 4, squareSize))
    overlay.set_alpha(230)
    overlay.fill(p.Color("darkgoldenrod"))
    screen.blit(overlay, (0, destRow * squareSize))
    for i, pieceType in enumerate(PROMOTION_ORDER):
        piece = color + pieceType
        screen.blit(IMAGES[piece], (i * squareSize, destRow * squareSize))


if __name__ == "__main__":
    main()
