import pygame
import os
from pygame.locals import *
import sys

# Initialize pygame
pygame.init()

# Screen dimensions
WIDTH, HEIGHT = 800, 800
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess 2D")

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HIGHLIGHT = (100, 255, 100, 150)
SELECTED = (255, 255, 100, 150)

# Board configuration
BOARD_SIZE = 8
SQUARE_SIZE = WIDTH // BOARD_SIZE

class ChessGame:
    def __init__(self):
        self.board = self.initialize_board()
        self.selected_piece = None
        self.current_turn = 'white'
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.move_log = []
        self.load_images()

    def load_images(self):
        # Load board images
        self.boards = {}
        board_dir = os.path.join('boards')
        for file in os.listdir(board_dir):
            if file.endswith('.svg'):
                try:
                    board_name = file.split('.')[0]
                    image = pygame.image.load(os.path.join(board_dir, file))
                    self.boards[board_name] = pygame.transform.scale(image, (WIDTH, HEIGHT))
                except:
                    print(f"Couldn't load board: {file}")

        # Default to rect-8x8 if available
        self.current_board = self.boards.get('rect-8x8', None)

        # Load piece images
        self.pieces = {}
        piece_dir = os.path.join('pieces')
        for file in os.listdir(piece_dir):
            if file.endswith('.svg'):
                try:
                    piece_name = file.split('.')[0]
                    image = pygame.image.load(os.path.join(piece_dir, file))
                    # Scale to fit square (adjust size as needed)
                    self.pieces[piece_name] = pygame.transform.scale(image, (SQUARE_SIZE-10, SQUARE_SIZE-10))
                except:
                    print(f"Couldn't load piece: {file}")

    def initialize_board(self):
        board = [[None for _ in range(8)] for _ in range(8)]
        for col in range(8):
            board[1][col] = {'type': 'pawn', 'color': 'black'}
            board[6][col] = {'type': 'pawn', 'color': 'white'}
        
        pieces = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
        for col, piece in enumerate(pieces):
            board[0][col] = {'type': piece, 'color': 'black'}
            board[7][col] = {'type': piece, 'color': 'white'}
        return board

    def pos_to_notation(self, row, col):
        letters = 'abcdefgh'
        return f"{letters[col]}{8 - row}"

    def is_valid_move(self, start, end):
        piece = self.board[start[0]][start[1]]
        if not piece or piece['color'] != self.current_turn:
            return False
        target = self.board[end[0]][end[1]]
        if target and target['color'] == piece['color']:
            return False
        
        row_diff = abs(end[0] - start[0])
        col_diff = abs(end[1] - start[1])

        if piece['type'] == 'pawn':
            direction = -1 if piece['color'] == 'white' else 1
            if start[1] == end[1]:
                if end[0] == start[0] + direction and not target:
                    return True
                if ((start[0] == 6 and piece['color'] == 'white') or 
                    (start[0] == 1 and piece['color'] == 'black')) and \
                    end[0] == start[0] + 2 * direction and not target:
                    return True
            elif row_diff == 1 and col_diff == 1 and target:
                return True
            return False
        elif piece['type'] == 'rook':
            return (row_diff == 0 or col_diff == 0)
        elif piece['type'] == 'knight':
            return (row_diff == 2 and col_diff == 1) or (row_diff == 1 and col_diff == 2)
        elif piece['type'] == 'bishop':
            return row_diff == col_diff
        elif piece['type'] == 'queen':
            return row_diff == col_diff or row_diff == 0 or col_diff == 0
        elif piece['type'] == 'king':
            return row_diff <= 1 and col_diff <= 1
        return False

    def move_piece(self, start, end):
        if self.is_valid_move(start, end):
            piece = self.board[start[0]][start[1]]
            target = self.board[end[0]][end[1]]
            
            if target and target['type'] == 'king':
                self.game_over = True
                self.winner = self.current_turn
            
            self.board[end[0]][end[1]] = piece
            self.board[start[0]][start[1]] = None

            move_text = f"{self.current_turn}: {piece['type']} {self.pos_to_notation(*start)} → {self.pos_to_notation(*end)}"
            self.move_log.append(move_text)
            self.current_turn = 'black' if self.current_turn == 'white' else 'white'
            return True
        return False

def draw_board(game):
    # Draw the selected board or default chess board
    if game.current_board:
        screen.blit(game.current_board, (0, 0))
    else:
        # Fallback: draw a simple chess board
        for row in range(8):
            for col in range(8):
                color = WHITE if (row + col) % 2 == 0 else BLACK
                pygame.draw.rect(screen, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))

    # Highlight selected piece and valid moves
    if game.selected_piece:
        row, col = game.selected_piece
        s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
        s.fill(SELECTED)
        screen.blit(s, (col * SQUARE_SIZE, row * SQUARE_SIZE))
        
        for move in game.valid_moves:
            r, c = move
            s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
            s.fill(HIGHLIGHT)
            screen.blit(s, (c * SQUARE_SIZE, r * SQUARE_SIZE))

    # Draw pieces
    for row in range(8):
        for col in range(8):
            piece = game.board[row][col]
            if piece:
                piece_key = f"{piece['type']}-{piece['color'][0]}"  # e.g., "pawn-w", "rook-b"
                piece_img = game.pieces.get(piece_key, None)
                if piece_img:
                    screen.blit(piece_img, 
                              (col * SQUARE_SIZE + 5, row * SQUARE_SIZE + 5))

def draw_move_log(game):
    font = pygame.font.SysFont('Arial', 16)
    log_x = 650
    log_y = 20
    
    # Draw log background
    pygame.draw.rect(screen, (50, 50, 50), (log_x - 10, log_y - 10, 150, 760))
    
    # Draw last 20 moves (or fewer)
    for i, move in enumerate(reversed(game.move_log[-20:])):
        text = font.render(move, True, WHITE)
        screen.blit(text, (log_x, log_y + i * 30))

def main():
    clock = pygame.time.Clock()
    game = ChessGame()
    
    while True:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
            
            elif event.type == MOUSEBUTTONDOWN:
                if event.button == 1:  # Left click
                    col = event.pos[0] // SQUARE_SIZE
                    row = event.pos[1] // SQUARE_SIZE
                    
                    if 0 <= row < 8 and 0 <= col < 8:
                        if not game.selected_piece and game.board[row][col] and game.board[row][col]['color'] == game.current_turn:
                            game.selected_piece = (row, col)
                            game.valid_moves = [(r, c) for r in range(8) for c in range(8)
                                              if game.is_valid_move((row, col), (r, c))]
                        elif game.selected_piece:
                            if (row, col) in game.valid_moves:
                                game.move_piece(game.selected_piece, (row, col))
                            game.selected_piece = None
                            game.valid_moves = []
            
            elif event.type == KEYDOWN:
                if event.key == K_ESCAPE:
                    game.selected_piece = None
                    game.valid_moves = []
                elif event.key == K_b:  # Change board
                    if game.boards:
                        current = list(game.boards.keys()).index(game.current_board.split('/')[-1].split('.')[0]) if game.current_board else -1
                        next_board = list(game.boards.keys())[(current + 1) % len(game.boards)]
                        game.current_board = game.boards[next_board]
        
        # Draw everything
        screen.fill((0, 0, 0))
        draw_board(game)
        draw_move_log(game)
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()