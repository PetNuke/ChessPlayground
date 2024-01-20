# Handles user input and displaying current game state

import pygame as p
import ChessEngine

width = height = 512
dimension = 8

squareSize = height// dimension

maxFPS = 15 # for animations
IMAGES = {}


"""
Initialize a global dictionary of images. Called once
"""
def loadImages():
    pieces = ["wp", "wR", "wN", "wB", "wK", "wQ", "bp", "bR", "bN", "bB", "bK", "bQ"]

    for x in pieces:
        IMAGES[x] = p.transform.scale(p.image.load("images/" + x + ".png"), (squareSize, squareSize))


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
    print(validMoves[0])
    moveMade = False


    loadImages()
    running = True
    squareSelected = ()
    playerClicks = []

    print("Game Start")

    while running:
        for e in p.event.get():
            if e.type == p.QUIT:
                running = False

            # mouse handler
            elif e.type == p.MOUSEBUTTONDOWN: # could add functionality to drag and drop
                location = p.mouse.get_pos() # col, row
                col = location[0]//squareSize
                row = location[1]//squareSize
                if squareSelected == (row, col): # deselect
                    squareSelected = ()
                    playerClicks = []
                else:
                    squareSelected = (row, col)
                    playerClicks.append(squareSelected)
                if len(playerClicks) == 2:
                    move = ChessEngine.Move(playerClicks[0], playerClicks[1], gs.board)
                    if move in validMoves:
                        gs.makeMove(move)
                        moveMade = True

                    # reset user clicks
                    squareSelected = ()
                    playerClicks = []

            # key handler
            elif e.type == p.KEYDOWN:
                if e.key == p.K_LEFT:
                    gs.undoMove()
                    moveMade = True

        if moveMade:
            validMoves = gs.getValidMoves()
            moveMade = False

            if gs.whiteToMove:
                print("White's turn")
            else:
                print("Black's turn")


        clock.tick(maxFPS)
        p.display.flip()

        drawGameState(screen, gs, playerClicks)


"""
Responsible for graphics
"""
def drawGameState(screen, gs, playerClicks):
    drawBoard(screen, playerClicks)
    drawPieces(screen, gs.board)


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
        color = color.lerp(p.Color('red'), .1)
        p.draw.rect(screen, color, p.Rect(selectedSquare[1] * squareSize, selectedSquare[0] * squareSize, squareSize, squareSize))


def drawPieces(screen, board):
    for row in range(dimension):
        for col in range(dimension):
            piece = board[row][col]
            if piece != "--":
                screen.blit(IMAGES[piece], (col*squareSize, row*squareSize))


if __name__ == "__main__":
    main()

