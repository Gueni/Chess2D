import pygame
import os
from pygame.locals import *
import sys

# Initialize pygame
pygame.init()
# Load the window icon
try:
    icon = pygame.image.load('D:/WORKSPACE/Chess2D/chess.png')
    pygame.display.set_icon(icon)
except:
    try:
        # Create a simple fallback icon
        icon = pygame.Surface((32, 32))
        icon.fill((50, 50, 50))  # Dark background
        pygame.draw.rect(icon, (200, 150, 50), (4, 4, 24, 24))  # Chess board
        pygame.display.set_icon(icon)
    except Exception as e:
        print(f"Could not set window icon: {e}")
# Screen dimensions
WIDTH, HEIGHT = 1050, 700
BOARD_SIZE = 700
SQUARE_SIZE = BOARD_SIZE // 8
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess 2D")
# Colors
LIGHT_BROWN = (240, 217, 181)
DARK_BROWN = (181, 136, 99)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
HIGHLIGHT = (100, 255, 100, 150)
SELECTED = (255, 255, 100, 150)
CHECK = (255, 0, 0, 150)
PROMOTION_BG = (70, 70, 70)
COORD_COLOR = (120, 120, 120)
# Font
font = pygame.font.SysFont('Arial', 18)
large_font = pygame.font.SysFont('Arial', 24)
coord_font = pygame.font.SysFont('Arial', 16, bold=True)

class ChessGame:
    def __init__(self):
        self.board = self.initialize_board()
        self.selected_piece = None
        self.current_turn = 'white'
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.move_log = []
        self.en_passant_target = None
        self.white_castling = {'kingside': True, 'queenside': True}
        self.black_castling = {'kingside': True, 'queenside': True}
        self.check = False
        self.promoting_pawn = None
        self.load_images()

    def load_images(self):
        self.pieces = {}
        piece_dir = os.path.join('pieces') if os.path.exists('pieces') else None
        
        # If pieces directory doesn't exist, we'll use colored circles as fallback
        if piece_dir:
            for file in os.listdir(piece_dir):
                if file.endswith('.svg') or file.endswith('.png'):
                    try:
                        piece_name = file.split('.')[0]
                        image = pygame.image.load(os.path.join(piece_dir, file))
                        self.pieces[piece_name] = pygame.transform.scale(image, (SQUARE_SIZE, SQUARE_SIZE))
                    except Exception as e:
                        print(f"Couldn't load piece {file}: {e}")
        else:
            # Create fallback piece representations
            for color in ['white', 'black']:
                for piece_type in ['pawn', 'rook', 'knight', 'bishop', 'queen', 'king']:
                    key = f"{piece_type}-{color[0]}"
                    surf = pygame.Surface((SQUARE_SIZE-10, SQUARE_SIZE-10), pygame.SRCALPHA)
                    col = (255, 255, 255) if color == 'white' else (50, 50, 50)
                    pygame.draw.circle(surf, col, (SQUARE_SIZE//2-5, SQUARE_SIZE//2-5), SQUARE_SIZE//2-15)
                    
                    # Add letter for piece type
                    letter = piece_type[0].upper() if piece_type != 'knight' else 'N'
                    text = coord_font.render(letter, True, (0, 0, 0) if color == 'white' else (255, 255, 255))
                    text_rect = text.get_rect(center=(SQUARE_SIZE//2-5, SQUARE_SIZE//2-5))
                    surf.blit(text, text_rect)
                    
                    self.pieces[key] = surf

    def initialize_board(self):
        board = [[None for _ in range(8)] for _ in range(8)]
        # Pawns
        for col in range(8):
            board[1][col] = {'type': 'pawn', 'color': 'black', 'moved': False}
            board[6][col] = {'type': 'pawn', 'color': 'white', 'moved': False}
        
        # Other pieces
        pieces = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
        for col, piece in enumerate(pieces):
            board[0][col] = {'type': piece, 'color': 'black', 'moved': False}
            board[7][col] = {'type': piece, 'color': 'white', 'moved': False}
        return board

    def pos_to_notation(self, row, col):
        letters = 'abcdefgh'
        return f"{letters[col]}{8 - row}"

    def is_in_check(self, color):
        king_pos = None
        # Find the king
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece and piece['type'] == 'king' and piece['color'] == color:
                    king_pos = (row, col)
                    break
            if king_pos:
                break
        
        # Check if any opponent piece can attack the king
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece and piece['color'] != color:
                    if self.is_valid_move((row, col), king_pos, check_check=False):
                        return True
        return False

    def is_valid_move(self, start, end, check_check=True):
        start_row, start_col = start
        end_row, end_col = end
        
        # Check if positions are within bounds
        if not (0 <= start_row < 8 and 0 <= start_col < 8 and 0 <= end_row < 8 and 0 <= end_col < 8):
            return False

        piece = self.board[start_row][start_col]
        if not piece or piece['color'] != self.current_turn:
            return False

        target = self.board[end_row][end_col]
        if target and target['color'] == piece['color']:
            return False

        # First check if the move follows the piece's movement rules
        row_diff = end_row - start_row
        col_diff = end_col - start_col
        abs_row = abs(row_diff)
        abs_col = abs(col_diff)

        # Pawn movement
        if piece['type'] == 'pawn':
            direction = -1 if piece['color'] == 'white' else 1
            
            # Forward move
            if start_col == end_col and target is None:
                if end_row == start_row + direction:
                    pass  # Valid single move
                elif ((start_row == 6 and piece['color'] == 'white') or 
                    (start_row == 1 and piece['color'] == 'black')) and \
                    end_row == start_row + 2 * direction and \
                    self.board[start_row + direction][start_col] is None:
                    pass  # Valid double move
                else:
                    return False
                
            # Capture
            elif abs_col == 1 and end_row == start_row + direction:
                # Normal capture
                if target:
                    pass  # Valid capture
                # En passant
                elif (end_row, end_col) == self.en_passant_target:
                    pass  # Valid en passant
                else:
                    return False
            else:
                return False

        # Rook movement
        elif piece['type'] == 'rook':
            if abs_row == 0 or abs_col == 0:
                # Check if path is clear
                step_row = 0 if abs_row == 0 else (1 if row_diff > 0 else -1)
                step_col = 0 if abs_col == 0 else (1 if col_diff > 0 else -1)
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row or current_col != end_col:
                    if self.board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
            else:
                return False

        # Knight movement
        elif piece['type'] == 'knight':
            if not ((abs_row == 2 and abs_col == 1) or (abs_row == 1 and abs_col == 2)):
                return False

        # Bishop movement
        elif piece['type'] == 'bishop':
            if abs_row == abs_col:
                step_row = 1 if row_diff > 0 else -1
                step_col = 1 if col_diff > 0 else -1
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row and current_col != end_col:
                    if self.board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
            else:
                return False

        # Queen movement
        elif piece['type'] == 'queen':
            if abs_row == abs_col or abs_row == 0 or abs_col == 0:
                step_row = 0 if abs_row == 0 else (1 if row_diff > 0 else -1)
                step_col = 0 if abs_col == 0 else (1 if col_diff > 0 else -1)
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row or current_col != end_col:
                    if self.board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
            else:
                return False

        # King movement
        elif piece['type'] == 'king':
            # Normal move
            if abs_row <= 1 and abs_col <= 1:
                pass  # Valid king move
            # Castling
            elif not piece['moved'] and abs_row == 0 and abs_col == 2:
                # Kingside castling
                if col_diff > 0:
                    rook_col = 7
                    if not (self.board[start_row][rook_col] and 
                        self.board[start_row][rook_col]['type'] == 'rook' and 
                        not self.board[start_row][rook_col]['moved'] and 
                        self.board[start_row][5] is None and 
                        self.board[start_row][6] is None):
                        return False
                # Queenside castling
                else:
                    rook_col = 0
                    if not (self.board[start_row][rook_col] and 
                        self.board[start_row][rook_col]['type'] == 'rook' and 
                        not self.board[start_row][rook_col]['moved'] and 
                        self.board[start_row][1] is None and 
                        self.board[start_row][2] is None and 
                        self.board[start_row][3] is None):
                        return False
                
                # Additional castling checks will be done in the check_check section
            else:
                return False

        # After verifying the move follows piece rules, check if it leaves king in check
        if check_check:
            # Simulate the move
            temp_board = [row[:] for row in self.board]
            temp_board[end_row][end_col] = piece
            temp_board[start_row][start_col] = None
            
            # Find the king's new position (it might be the moving piece)
            king_pos = None
            for r in range(8):
                for c in range(8):
                    p = temp_board[r][c]
                    if p and p['type'] == 'king' and p['color'] == piece['color']:
                        king_pos = (r, c)
                        break
                if king_pos:
                    break
            
            # Check if any opponent piece can attack the king
            for r in range(8):
                for c in range(8):
                    p = temp_board[r][c]
                    if p and p['color'] != piece['color']:
                        if self.simulated_is_valid_move((r, c), king_pos, p, temp_board):
                            return False

        return True

    def would_be_in_check(self, start, end):
        # Simulate move and check if king would be in check
        temp_board = [row[:] for row in self.board]
        piece = temp_board[start[0]][start[1]]
        temp_board[end[0]][end[1]] = piece
        temp_board[start[0]][start[1]] = None
        
        # Find the king
        king_pos = None
        for row in range(8):
            for col in range(8):
                p = temp_board[row][col]
                if p and p['type'] == 'king' and p['color'] == piece['color']:
                    king_pos = (row, col)
                    break
            if king_pos:
                break
        
        # Check if any opponent piece can attack the king
        for row in range(8):
            for col in range(8):
                p = temp_board[row][col]
                if p and p['color'] != piece['color']:
                    if self.simulated_is_valid_move((row, col), king_pos, p, temp_board):
                        return True
        return False

    def simulated_is_valid_move(self, start, end, piece, board):
        start_row, start_col = start
        end_row, end_col = end
        
        row_diff = end_row - start_row
        col_diff = end_col - start_col
        abs_row = abs(row_diff)
        abs_col = abs(col_diff)

        target = board[end_row][end_col]
        if target and target['color'] == piece['color']:
            return False

        if piece['type'] == 'pawn':
            direction = -1 if piece['color'] == 'white' else 1
            if start_col == end_col and target is None:
                if end_row == start_row + direction:
                    return True
                if ((start_row == 6 and piece['color'] == 'white') or 
                    (start_row == 1 and piece['color'] == 'black')) and \
                    end_row == start_row + 2 * direction and \
                    board[start_row + direction][start_col] is None:
                    return True
            elif abs_col == 1 and end_row == start_row + direction and target:
                return True
            return False
        elif piece['type'] == 'rook':
            if abs_row == 0 or abs_col == 0:
                step_row = 0 if abs_row == 0 else (1 if row_diff > 0 else -1)
                step_col = 0 if abs_col == 0 else (1 if col_diff > 0 else -1)
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row or current_col != end_col:
                    if board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
                return True
            return False
        elif piece['type'] == 'knight':
            return (abs_row == 2 and abs_col == 1) or (abs_row == 1 and abs_col == 2)
        elif piece['type'] == 'bishop':
            if abs_row == abs_col:
                step_row = 1 if row_diff > 0 else -1
                step_col = 1 if col_diff > 0 else -1
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row and current_col != end_col:
                    if board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
                return True
            return False
        elif piece['type'] == 'queen':
            if abs_row == abs_col or abs_row == 0 or abs_col == 0:
                step_row = 0 if abs_row == 0 else (1 if row_diff > 0 else -1)
                step_col = 0 if abs_col == 0 else (1 if col_diff > 0 else -1)
                
                current_row, current_col = start_row + step_row, start_col + step_col
                while current_row != end_row or current_col != end_col:
                    if board[current_row][current_col] is not None:
                        return False
                    current_row += step_row
                    current_col += step_col
                return True
            return False
        elif piece['type'] == 'king':
            return abs_row <= 1 and abs_col <= 1
        return False

    def move_piece(self, start, end):
        start_row, start_col = start
        end_row, end_col = end
        
        if not self.is_valid_move(start, end):
            return False

        piece = self.board[start_row][start_col]
        target = self.board[end_row][end_col]
        
        # Check for pawn promotion
        if piece['type'] == 'pawn' and (end_row == 0 or end_row == 7):
            self.promoting_pawn = (end_row, end_col)
            # Make sure the piece is still there
            self.board[end_row][end_col] = piece
            self.board[start_row][start_col] = None
            return True

        # Handle en passant
        if piece['type'] == 'pawn' and (end_row, end_col) == self.en_passant_target:
            # Remove the captured pawn
            captured_row = start_row
            captured_col = end_col
            self.board[captured_row][captured_col] = None

        # Handle castling
        if piece['type'] == 'king' and abs(start_col - end_col) == 2:
            # Kingside castling
            if end_col > start_col:
                rook_start_col = 7
                rook_end_col = 5
            # Queenside castling
            else:
                rook_start_col = 0
                rook_end_col = 3
            
            # Move the rook
            rook = self.board[start_row][rook_start_col]
            self.board[start_row][rook_end_col] = rook
            self.board[start_row][rook_start_col] = None
            if rook:
                rook['moved'] = True

        # Update en passant target
        self.en_passant_target = None
        if piece['type'] == 'pawn' and abs(start_row - end_row) == 2:
            self.en_passant_target = (start_row + (end_row - start_row) // 2, start_col)

        # Update castling rights
        if piece['type'] == 'king':
            if piece['color'] == 'white':
                self.white_castling = {'kingside': False, 'queenside': False}
            else:
                self.black_castling = {'kingside': False, 'queenside': False}
        elif piece['type'] == 'rook':
            if piece['color'] == 'white':
                if start_col == 0:
                    self.white_castling['queenside'] = False
                elif start_col == 7:
                    self.white_castling['kingside'] = False
            else:
                if start_col == 0:
                    self.black_castling['queenside'] = False
                elif start_col == 7:
                    self.black_castling['kingside'] = False

        # Make the move
        self.board[end_row][end_col] = piece
        self.board[start_row][start_col] = None
        piece['moved'] = True

        # Reset check status before checking new state
        self.check = False
        
        # Check if this move puts the opponent in check
        opponent_color = 'black' if self.current_turn == 'white' else 'white'
        self.check = self.is_in_check(opponent_color)

        # Log the move
        move_notation = self.get_move_notation(start, end, piece, target)
        self.move_log.append(move_notation)

        # Switch turns
        self.current_turn = opponent_color

        # Only check for checkmate/stalemate after the opponent has moved
        return True
    
    def get_move_notation(self, start, end, piece, target):
        letters = 'abcdefgh'
        start_col, start_row = letters[start[1]], 8 - start[0]
        end_col, end_row = letters[end[1]], 8 - end[0]
        
        # Castling
        if piece['type'] == 'king' and abs(start[1] - end[1]) == 2:
            return "O-O" if end[1] > start[1] else "O-O-O"
        
        # Piece notation
        piece_letter = ''
        if piece['type'] != 'pawn':
            piece_letter = piece['type'][0].upper()
        
        # Capture
        capture = 'x' if target else ''
        
        # Check/checkmate
        check = ''
        opponent_color = 'black' if piece['color'] == 'white' else 'white'
        if self.is_in_check(opponent_color):
            check = '+' if not self.game_over else '#'
        
        return f"{piece_letter}{letters[start[1]]}{start_row}{capture}{end_col}{end_row}{check}"

    def promote_pawn(self, piece_type):
        if not self.promoting_pawn:
            return False
        
        row, col = self.promoting_pawn
        if not (0 <= row < 8 and 0 <= col < 8):
            return False
        
        piece = self.board[row][col]
        if not piece or piece['type'] != 'pawn':
            return False
        
        # Promote the pawn
        piece['type'] = piece_type
        
        # Log the promotion
        promotion_notation = f"{self.pos_to_notation(row, col)}={piece_type[0].upper()}"
        if self.move_log:
            self.move_log[-1] += promotion_notation
        
        # Complete the move
        self.promoting_pawn = None
        
        # Check if this puts the opponent in check
        opponent_color = 'black' if self.current_turn == 'white' else 'white'
        self.check = self.is_in_check(opponent_color)
        
        # Switch turns
        self.current_turn = opponent_color
        
        return True

def draw_board(game):
    # Draw the chess board with coordinates
    for row in range(8):
        for col in range(8):
            color = LIGHT_BROWN if (row + col) % 2 == 0 else DARK_BROWN
            pygame.draw.rect(screen, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))
    
    # Draw coordinates (letters a-h)
    letters = 'abcdefgh'
    for col in range(8):
        letter = coord_font.render(letters[col], True, COORD_COLOR)
        # Bottom coordinates
        screen.blit(letter, (col * SQUARE_SIZE + SQUARE_SIZE - 15, BOARD_SIZE - 20))
        # Top coordinates (upside down)
        screen.blit(letter, (col * SQUARE_SIZE + 5, 5))
    
    # Draw coordinates (numbers 1-8)
    for row in range(8):
        number = coord_font.render(str(8 - row), True, COORD_COLOR)
        # Left coordinates
        screen.blit(number, (5, row * SQUARE_SIZE + 5))
        # Right coordinates
        screen.blit(number, (BOARD_SIZE - 15, row * SQUARE_SIZE + SQUARE_SIZE - 20))

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

    # Highlight king in check
    for row in range(8):
        for col in range(8):
            piece = game.board[row][col]
            if piece and piece['type'] == 'king' and game.is_in_check(piece['color']):
                s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                s.fill(CHECK)
                screen.blit(s, (col * SQUARE_SIZE, row * SQUARE_SIZE))
                break

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

def draw_promotion_menu(game):
    if not game.promoting_pawn:
        return
    
    row, col = game.promoting_pawn
    piece = game.board[row][col]
    
    # Add this check to prevent the error
    if not piece:
        return
    
    color = piece['color']
    
    # Draw background
    menu_x = col * SQUARE_SIZE
    menu_y = row * SQUARE_SIZE if row == 0 else row * SQUARE_SIZE - 3 * SQUARE_SIZE
    menu_width = SQUARE_SIZE
    menu_height = 4 * SQUARE_SIZE
    
    pygame.draw.rect(screen, PROMOTION_BG, (menu_x, menu_y, menu_width, menu_height))
    pygame.draw.rect(screen, WHITE, (menu_x, menu_y, menu_width, menu_height), 2)
    
    # Draw pieces to promote to
    pieces = ['queen', 'rook', 'bishop', 'knight']
    for i, piece_type in enumerate(pieces):
        piece_key = f"{piece_type}-{color[0]}"
        piece_img = game.pieces.get(piece_key, None)
        if piece_img:
            screen.blit(piece_img, (menu_x + 5, menu_y + i * SQUARE_SIZE + 5))

def draw_move_log(game):
    log_x = BOARD_SIZE + 10
    log_y = 10
    log_width = WIDTH - BOARD_SIZE - 20
    log_height = HEIGHT - 20
    
    # Draw log background
    pygame.draw.rect(screen, (50, 50, 50), (log_x - 5, log_y - 5, log_width + 10, log_height + 10))
    pygame.draw.rect(screen, (100, 100, 100), (log_x, log_y, log_width, log_height))
    
    # Draw title
    title = large_font.render("Move Log", True, WHITE)
    screen.blit(title, (log_x + (log_width - title.get_width()) // 2, log_y + 10))
    
    # Draw moves
    move_y = log_y + 50
    move_number = 1
    
    # Pair moves (white and black)
    for i in range(0, len(game.move_log), 2):
        # Move number
        num_text = font.render(f"{move_number}.", True, WHITE)
        screen.blit(num_text, (log_x + 10, move_y))
        
        # White move
        if i < len(game.move_log):
            white_move = font.render(game.move_log[i], True, WHITE)
            screen.blit(white_move, (log_x + 50, move_y))
        
        # Black move (if exists)
        if i + 1 < len(game.move_log):
            black_move = font.render(game.move_log[i+1], True, WHITE)
            screen.blit(black_move, (log_x + 150, move_y))
        
        move_y += 30
        move_number += 1
        
        # Stop if we're running out of space
        if move_y > log_y + log_height - 30:
            break

def draw_game_status(game):
    status_y = HEIGHT - 40
    # Current turn
    turn_text = f"Current Turn: {game.current_turn.capitalize()}"
    if game.check:
        turn_text += " (CHECK!)"
    if game.game_over:
        if game.winner:
            turn_text = f"Game Over! {game.winner.capitalize()} wins by checkmate!"
        else:
            turn_text = "Game Over! Stalemate!"
    
    status_surface = large_font.render(turn_text, True, WHITE)
    screen.blit(status_surface, (10, status_y))

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
                    
                    # Check if we're promoting a pawn
                    if game.promoting_pawn:
                        promo_row, promo_col = game.promoting_pawn
                        if (col == promo_col and 
                            ((promo_row == 0 and row in [0, 1, 2, 3]) or 
                             (promo_row == 7 and row in [4, 5, 6, 7]))):
                            # Determine which piece was selected
                            if promo_row == 0:  # White promoting at top
                                piece_index = row
                            else:  # Black promoting at bottom
                                piece_index = 3 - (row - 4)
                            
                            pieces = ['queen', 'rook', 'bishop', 'knight']
                            game.promote_pawn(pieces[piece_index])
                        continue
                    
                    # Normal move selection
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
                    game.promoting_pawn = None
        
        # Draw everything
        screen.fill((0, 0, 0))
        draw_board(game)
        draw_promotion_menu(game)
        draw_move_log(game)
        draw_game_status(game)
        
        pygame.display.flip()
        clock.tick(60)

if __name__ == "__main__":
    main()