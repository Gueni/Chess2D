
#!/usr/bin/env python
# coding=utf-8
#? -------------------------------------------------------------------------------
#?
#?                 ________  __________________    ___   ____ 
#?                / ____/ / / / ____/ ___/ ___/   |__ \ / __ \
#?               / /   / /_/ / __/  \__ \\__ \    __/ // / / /
#?              / /___/ __  / /___ ___/ /__/ /   / __// /_/ / 
#?              \____/_/ /_/_____//____/____/   /____/_____/  
#?
#? Name:        chess_game.py
#? Purpose:     A 2D Chess game with AI opponent using Stockfish
#?
#? Author:      Mohamed Gueni (mohamedgueni@outlook.com)
#? Based on:    python-chess library & Stockfish engine
#? Created:     06/06/2025
#? Version:     0.2
#? Licence:     Refer to the LICENSE file
#? -------------------------------------------------------------------------------
import subprocess
import pygame
import os
from pygame.locals import *
import sys
import chess
import chess.engine
import platform
import tkinter as tk
from tkinter import filedialog
#? -------------------------------------------------------------------------------
pygame.init()                                                      
script_dir      = os.path.dirname(os.path.abspath(__file__))  
image_path      = os.path.join(script_dir, 'chess.png')  
icon            = pygame.image.load(image_path)  
pygame.display.set_icon(icon)
WIDTH, HEIGHT   = 1050, 700
BOARD_SIZE      = 700
SQUARE_SIZE     = BOARD_SIZE // 8
screen          = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Chess 2D")
BUTTON_COLOR    = (70, 70, 70)
BUTTON_HOVER    = (100, 100, 100)
BUTTON_TEXT     = (255, 255, 255)
BUTTON_WIDTH    = 150
BUTTON_HEIGHT   = 40
LIGHT_BROWN     = (240, 217, 181)
DARK_BROWN      = (181, 136, 99)
WHITE           = (255, 255, 255)
BLACK           = (0, 0, 0)
HIGHLIGHT       = (100, 255, 100, 150)
SELECTED        = (255, 255, 100, 150)
CHECK           = (255, 0, 0, 150)
PROMOTION_BG    = (70, 70, 70)
COORD_COLOR     = (120, 120, 120)
font            = pygame.font.SysFont('Arial', 18)
large_font      = pygame.font.SysFont('Arial', 24)
coord_font      = pygame.font.SysFont('Arial', 16, bold=True)
#? -------------------------------------------------------------------------------
class ChessEngine:
    def __init__(self):
        self.engine_dir     = os.path.join(os.path.dirname(__file__), "stockfish")
        self.engine_path    = self._get_engine_path()

    def _get_engine_path(self):
        system              = platform.system()
        if system == "Windows":
            exe_name        = "stockfish-windows-x86-64-avx2.exe"
        elif system == "Linux":
            exe_name        = "stockfish-ubuntu-x86-64-avx2"    # Linux
        elif system == "Darwin":                               
            exe_name        = "stockfish-macos-x86-64-avx2"     # macOS
        else:
            raise OSError(f"Unsupported OS: {system}")
        path                = os.path.join(self.engine_dir, exe_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Stockfish engine not found at: {path}")
        return path

pygame.mixer.init()
SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR       = os.path.join(SCRIPT_DIR, "sound")

def load_sound(filename):
    return pygame.mixer.Sound(os.path.join(SOUND_DIR, filename))

capture_sound   = load_sound("capture.mp3")
castle_sound    = load_sound("castle.mp3")
check_sound     = load_sound("check.mp3")
move_sound      = load_sound("move.mp3")
notify_sound    = load_sound("notify.mp3")
promote_sound   = load_sound("promote.mp3")
SOUND_ENABLED   = True

class ChessGame:
    def __init__(self, player_color='white'):
        self.log_scroll         = 0 
        self.board              = self.initialize_board()
        self.selected_piece     = None
        self.current_turn       = 'white'
        self.valid_moves        = []
        self.game_over          = False
        self.winner             = None
        self.move_log           = []
        self.en_passant_target  = None
        self.white_castling     = {'kingside': True, 'queenside': True}
        self.black_castling     = {'kingside': True, 'queenside': True}
        self.check              = False
        self.promoting_pawn     = None
        self.load_images()
        self.engine_path        = ChessEngine()
        self.engine             = None
        self.player_color       = player_color 
        self.ai_thinking        = False
        self.init_stockfish()

    def init_stockfish(self):
        try:
            _DIR                = os.path.dirname(os.path.abspath(__file__))
            self.engine_path    = os.path.join(SCRIPT_DIR, "stockfish/stockfish-windows-x86-64-avx2.exe")
            
            if not os.path.exists(self.engine_path):
                raise FileNotFoundError(f"Stockfish not found at {self.engine_path}")
            
            if sys.platform == 'win32':
                startupinfo                 = subprocess.STARTUPINFO()
                startupinfo.dwFlags        |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow     = subprocess.SW_HIDE
                self.engine                 = chess.engine.SimpleEngine.popen_uci(self.engine_path,startupinfo=startupinfo)
            else:
                self.engine     = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            
        except Exception as e:
            print(f"Failed to initialize Stockfish: {e}")
            self.engine     = None

    def get_stockfish_move(self):
        if not self.engine: return None
        board       = self.convert_to_chess_board()
        try:
            result  = self.engine.play(board, chess.engine.Limit(time=0.5))
            return result.move
        except Exception as e:
            print(f"Error getting Stockfish move: {e}")
            return None

    def convert_to_chess_board(self):
        board   = chess.Board()
        board.clear()
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece:
                    color = chess.WHITE if piece['color'] == 'white' else chess.BLACK
                    square = chess.square(col, 7 - row)  
                    if piece['type'] == 'pawn':
                        board.set_piece_at(square, chess.Piece(chess.PAWN, color))
                    elif piece['type'] == 'rook':
                        board.set_piece_at(square, chess.Piece(chess.ROOK, color))
                    elif piece['type'] == 'knight':
                        board.set_piece_at(square, chess.Piece(chess.KNIGHT, color))
                    elif piece['type'] == 'bishop':
                        board.set_piece_at(square, chess.Piece(chess.BISHOP, color))
                    elif piece['type'] == 'queen':
                        board.set_piece_at(square, chess.Piece(chess.QUEEN, color))
                    elif piece['type'] == 'king':
                        board.set_piece_at(square, chess.Piece(chess.KING, color))
        
        # Set castling rights
        castling_rights = ""
        if self.white_castling['kingside'] and self.board[7][4] and self.board[7][4]['type'] == 'king' and self.board[7][4]['color'] == 'white':
            castling_rights += "K"
        if self.white_castling['queenside'] and self.board[7][4] and self.board[7][4]['type'] == 'king' and self.board[7][4]['color'] == 'white':
            castling_rights += "Q"
        if self.black_castling['kingside'] and self.board[0][4] and self.board[0][4]['type'] == 'king' and self.board[0][4]['color'] == 'black':
            castling_rights += "k"
        if self.black_castling['queenside'] and self.board[0][4] and self.board[0][4]['type'] == 'king' and self.board[0][4]['color'] == 'black':
            castling_rights += "q"
        board.set_castling_fen(castling_rights if castling_rights else "-")
        
        # Set en passant square
        if self.en_passant_target:
            ep_row, ep_col = self.en_passant_target
            board.ep_square = chess.square(ep_col, 7 - ep_row)
        else:
            board.ep_square = None
        
        # Set turn
        board.turn = chess.WHITE if self.current_turn == 'white' else chess.BLACK
        
        return board

    def make_ai_move(self):
        if self.current_turn != self.player_color and not self.game_over and not self.promoting_pawn:
            move = self.get_stockfish_move()
            if move:
                from_col    = chess.square_file(move.from_square)
                from_row    = 7 - chess.square_rank(move.from_square)
                to_col      = chess.square_file(move.to_square)
                to_row      = 7 - chess.square_rank(move.to_square)
                promotion = None
                if move.promotion:
                    if move.promotion == chess.QUEEN:
                        promotion = 'queen'
                    elif move.promotion == chess.ROOK:
                        promotion = 'rook'
                    elif move.promotion == chess.BISHOP:
                        promotion = 'bishop'
                    elif move.promotion == chess.KNIGHT:
                        promotion = 'knight'
                if self.move_piece((from_row, from_col), (to_row, to_col)):
                    if promotion and self.promoting_pawn:
                        self.promote_pawn(promotion)
                    return True
        return False

    def load_images(self):
        self.pieces     = {}
        piece_dir       = resource_path('pieces')
        if os.path.exists(piece_dir):
            for file in os.listdir(piece_dir):
                if file.endswith('.png') or file.endswith('.svg'):
                    try:
                        piece_name              = file.split('.')[0]
                        image_path              = os.path.join(piece_dir, file)
                        image                   = pygame.image.load(image_path)
                        self.pieces[piece_name] = pygame.transform.scale(image, (SQUARE_SIZE, SQUARE_SIZE))
                    except Exception as e:
                        print(f"Couldn't load piece {file}: {e}")
        else:
            for color in ['white', 'black']:
                for piece_type in ['pawn', 'rook', 'knight', 'bishop', 'queen', 'king']:
                    key                 = f"{piece_type}-{color[0]}"
                    surf                = pygame.Surface((SQUARE_SIZE-10, SQUARE_SIZE-10), pygame.SRCALPHA)
                    col                 = (255, 255, 255) if color == 'white' else (50, 50, 50)
                    pygame.draw.circle(surf, col, (SQUARE_SIZE//2-5, SQUARE_SIZE//2-5), SQUARE_SIZE//2-15)
                    letter              = piece_type[0].upper() if piece_type != 'knight' else 'N'
                    text                = coord_font.render(letter, True, (0, 0, 0) if color == 'white' else (255, 255, 255))
                    text_rect           = text.get_rect(center=(SQUARE_SIZE//2-5, SQUARE_SIZE//2-5))
                    surf.blit(text, text_rect)
                    self.pieces[key]    = surf

    def initialize_board(self):
        board                   = [[None for _ in range(8)] for _ in range(8)]
        for col in range(8):
            board[1][col]       = {'type': 'pawn', 'color': 'black', 'moved': False}
            board[6][col]       = {'type': 'pawn', 'color': 'white', 'moved': False}
        pieces                  = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
        for col, piece in enumerate(pieces):
            board[0][col]       = {'type': piece, 'color': 'black', 'moved': False}
            board[7][col]       = {'type': piece, 'color': 'white', 'moved': False}
        return board

    def pos_to_notation(self, row, col):
        letters     = 'abcdefgh'
        return f"{letters[col]}{8 - row}"

    def is_in_check(self, color):
        king_pos = None
        for row in range(8):
            for col in range(8):
                piece = self.board[row][col]
                if piece and piece['type'] == 'king' and piece['color'] == color:
                    king_pos = (row, col)
                    break
            if king_pos:
                break
        
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
        if not (0 <= start_row < 8 and 0 <= start_col < 8 and 0 <= end_row < 8 and 0 <= end_col < 8):
            return False
        piece = self.board[start_row][start_col]
        if not piece or piece['color'] != self.current_turn:
            return False
        target = self.board[end_row][end_col]
        if target and target['color'] == piece['color']:
            return False
        row_diff = end_row - start_row
        col_diff = end_col - start_col
        abs_row = abs(row_diff)
        abs_col = abs(col_diff)
        if piece['type'] == 'pawn':
            direction = -1 if piece['color'] == 'white' else 1
            if start_col == end_col and target is None:
                if end_row == start_row + direction:
                    pass
                elif ((start_row == 6 and piece['color'] == 'white') or 
                    (start_row == 1 and piece['color'] == 'black')) and \
                    end_row == start_row + 2 * direction and \
                    self.board[start_row + direction][start_col] is None:
                    pass
                else:
                    return False
            elif abs_col == 1 and end_row == start_row + direction:
                if target:
                    pass
                elif (end_row, end_col) == self.en_passant_target:
                    pass
                else:
                    return False
            else:
                return False
        elif piece['type'] == 'rook':
            if abs_row == 0 or abs_col == 0:
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
        elif piece['type'] == 'knight':
            if not ((abs_row == 2 and abs_col == 1) or (abs_row == 1 and abs_col == 2)):
                return False
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

        elif piece['type'] == 'king':
            if abs_row <= 1 and abs_col <= 1:
                pass
            elif not piece['moved'] and abs_row == 0 and abs_col == 2:
                if col_diff > 0:
                    rook_col = 7
                    if not (self.board[start_row][rook_col] and 
                        self.board[start_row][rook_col]['type'] == 'rook' and 
                        not self.board[start_row][rook_col]['moved'] and 
                        self.board[start_row][5] is None and 
                        self.board[start_row][6] is None):
                        return False
                else:
                    rook_col = 0
                    if not (self.board[start_row][rook_col] and 
                        self.board[start_row][rook_col]['type'] == 'rook' and 
                        not self.board[start_row][rook_col]['moved'] and 
                        self.board[start_row][1] is None and 
                        self.board[start_row][2] is None and 
                        self.board[start_row][3] is None):
                        return False
            else:
                return False

        if check_check:
            temp_board = [row[:] for row in self.board]
            temp_board[end_row][end_col] = piece
            temp_board[start_row][start_col] = None
            
            king_pos = None
            for r in range(8):
                for c in range(8):
                    p = temp_board[r][c]
                    if p and p['type'] == 'king' and p['color'] == piece['color']:
                        king_pos = (r, c)
                        break
                if king_pos:
                    break
            
            for r in range(8):
                for c in range(8):
                    p = temp_board[r][c]
                    if p and p['color'] != piece['color']:
                        if self.simulated_is_valid_move((r, c), king_pos, p, temp_board):
                            return False

        return True

    def would_be_in_check(self, start, end):
        temp_board = [row[:] for row in self.board]
        piece = temp_board[start[0]][start[1]]
        temp_board[end[0]][end[1]] = piece
        temp_board[start[0]][start[1]] = None
        
        king_pos = None
        for row in range(8):
            for col in range(8):
                p = temp_board[row][col]
                if p and p['type'] == 'king' and p['color'] == piece['color']:
                    king_pos = (row, col)
                    break
            if king_pos:
                break
        
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
        
        if piece['type'] == 'pawn' and (end_row == 0 or end_row == 7):
            self.promoting_pawn = (end_row, end_col)
            self.board[end_row][end_col] = piece
            self.board[start_row][start_col] = None
            if SOUND_ENABLED:
                notify_sound.play()
            return True
        if SOUND_ENABLED:
            if piece['type'] == 'king' and abs(start_col - end_col) == 2: 
                castle_sound.play()
            elif target:  
                capture_sound.play()
            else:  
                move_sound.play()
        if piece['type'] == 'pawn' and (end_row, end_col) == self.en_passant_target:
            captured_row = start_row
            captured_col = end_col
            self.board[captured_row][captured_col] = None
            if SOUND_ENABLED:
                capture_sound.play()

        if piece['type'] == 'king' and abs(start_col - end_col) == 2:
            if end_col > start_col:
                rook_start_col = 7
                rook_end_col = 5
            else:
                rook_start_col = 0
                rook_end_col = 3
            
            rook = self.board[start_row][rook_start_col]
            self.board[start_row][rook_end_col] = rook
            self.board[start_row][rook_start_col] = None
            if rook:
                rook['moved'] = True

        self.en_passant_target = None
        if piece['type'] == 'pawn' and abs(start_row - end_row) == 2:
            self.en_passant_target = (start_row + (end_row - start_row) // 2, start_col)

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

        self.board[end_row][end_col] = piece
        self.board[start_row][start_col] = None
        piece['moved'] = True

        self.check = False
        
        opponent_color = 'black' if self.current_turn == 'white' else 'white'
        self.check = self.is_in_check(opponent_color)
        
        if self.check and SOUND_ENABLED:
            check_sound.play()

        move_notation = self.get_move_notation(start, end, piece, target)
        self.move_log.append(move_notation)

        self.current_turn = opponent_color

        return True
    
    def get_move_notation(self, start, end, piece, target):
        letters = 'abcdefgh'
        start_col, start_row = letters[start[1]], 8 - start[0]
        end_col, end_row = letters[end[1]], 8 - end[0]
        
        if piece['type'] == 'king' and abs(start[1] - end[1]) == 2:
            return "O-O" if end[1] > start[1] else "O-O-O"
        
        piece_letter = ''
        if piece['type'] != 'pawn':
            piece_letter = piece['type'][0].upper()
        
        capture = 'x' if target else ''
        
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
        
        piece['type'] = piece_type
        
        if SOUND_ENABLED:
            promote_sound.play()
        
        promotion_notation = f"{self.pos_to_notation(row, col)}={piece_type[0].upper()}"
        if self.move_log:
            self.move_log[-1] += promotion_notation
        
        self.promoting_pawn = None
        
        opponent_color = 'black' if self.current_turn == 'white' else 'white'
        self.check = self.is_in_check(opponent_color)
        
        if self.check and SOUND_ENABLED:
            check_sound.play()
        
        self.current_turn = opponent_color
        
        return True

    def __del__(self):
        if self.engine:
            self.engine.quit()

    def export_move_log(self):
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()  # Hide the main window
            
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
                title="Save move log as",
                initialfile="chess_log.txt"
            )
            
            if file_path:  # Only proceed if user didn't cancel
                with open(file_path, "w") as f:
                    f.write("Chess Game Move Log\n")
                    f.write("==================\n\n")
                    for i in range(0, len(self.move_log), 2):
                        move_num = (i // 2) + 1
                        white_move = self.move_log[i] if i < len(self.move_log) else ""
                        black_move = self.move_log[i+1] if i+1 < len(self.move_log) else ""
                        f.write(f"{move_num}. {white_move}\t{black_move}\n")
                print(f"Move log exported to {file_path}")
                if SOUND_ENABLED:
                    notify_sound.play()
        except Exception as e:
            print(f"Error exporting move log: {e}")

    def reset_game(self):
        self.__init__(player_color=self.player_color)
        if SOUND_ENABLED:
            notify_sound.play()

class Button:
    def __init__(self, x, y, width, height, text):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.is_hovered = False
        
    def draw(self, surface):
        color = BUTTON_HOVER if self.is_hovered else BUTTON_COLOR
        pygame.draw.rect(surface, color, self.rect, border_radius=5)
        pygame.draw.rect(surface, WHITE, self.rect, 2, border_radius=5)
        
        text_surf = font.render(self.text, True, BUTTON_TEXT)
        text_rect = text_surf.get_rect(center=self.rect.center)
        surface.blit(text_surf, text_rect)
        
    def check_hover(self, pos):
        self.is_hovered = self.rect.collidepoint(pos)
        return self.is_hovered
        
    def is_clicked(self, pos, event):
        if event.type == MOUSEBUTTONDOWN and event.button == 1:
            return self.rect.collidepoint(pos)
        return False
    
def resource_path(relative_path):
    """Get the absolute path to a resource, works for dev and PyInstaller."""
    if hasattr(sys, '_MEIPASS'):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def draw_board(game):
    for row in range(8):
        for col in range(8):
            color = LIGHT_BROWN if (row + col) % 2 == 0 else DARK_BROWN
            pygame.draw.rect(screen, color, (col * SQUARE_SIZE, row * SQUARE_SIZE, SQUARE_SIZE, SQUARE_SIZE))
    
    letters = 'abcdefgh'
    for col in range(8):
        letter = coord_font.render(letters[col], True, COORD_COLOR)
        screen.blit(letter, (col * SQUARE_SIZE + SQUARE_SIZE - 15, BOARD_SIZE - 20))
        screen.blit(letter, (col * SQUARE_SIZE + 5, 5))
    
    for row in range(8):
        number = coord_font.render(str(8 - row), True, COORD_COLOR)
        screen.blit(number, (5, row * SQUARE_SIZE + 5))
        screen.blit(number, (BOARD_SIZE - 15, row * SQUARE_SIZE + SQUARE_SIZE - 20))

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

    for row in range(8):
        for col in range(8):
            piece = game.board[row][col]
            if piece and piece['type'] == 'king' and game.is_in_check(piece['color']):
                s = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE), pygame.SRCALPHA)
                s.fill(CHECK)
                screen.blit(s, (col * SQUARE_SIZE, row * SQUARE_SIZE))
                break

    for row in range(8):
        for col in range(8):
            piece = game.board[row][col]
            if piece:
                piece_key = f"{piece['type']}-{piece['color'][0]}"
                piece_img = game.pieces.get(piece_key, None)
                if piece_img:
                    screen.blit(piece_img, 
                              (col * SQUARE_SIZE + 5, row * SQUARE_SIZE + 5))

def draw_promotion_menu(game):
    if not game.promoting_pawn:
        return
    
    row, col = game.promoting_pawn
    piece = game.board[row][col]
    
    if not piece:
        return
    
    color = piece['color']
    
    menu_x = col * SQUARE_SIZE
    menu_y = row * SQUARE_SIZE if row == 0 else row * SQUARE_SIZE - 3 * SQUARE_SIZE
    menu_width = SQUARE_SIZE
    menu_height = 4 * SQUARE_SIZE
    
    pygame.draw.rect(screen, PROMOTION_BG, (menu_x, menu_y, menu_width, menu_height))
    pygame.draw.rect(screen, WHITE, (menu_x, menu_y, menu_width, menu_height), 2)
    
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
    
    # Create a surface for the log content that can be larger than the visible area
    log_content_height = max(HEIGHT, (len(game.move_log) // 2 + 2) * 30)
    log_content = pygame.Surface((log_width, log_content_height))
    log_content.fill((100, 100, 100))
    
    # Draw the log content
    title = large_font.render("Move Log", True, WHITE)
    log_content.blit(title, ((log_width - title.get_width()) // 2, 10))
    
    move_y = 50
    move_number = 1
    
    # Track the current scroll position (you'll need to add this as a game variable)
    if not hasattr(game, 'log_scroll'):
        game.log_scroll = 0
    
    for i in range(0, len(game.move_log), 2):
        num_text = font.render(f"{move_number}.", True, WHITE)
        log_content.blit(num_text, (10, move_y))
        
        if i < len(game.move_log):
            white_move = font.render(game.move_log[i], True, WHITE)
            log_content.blit(white_move, (50, move_y))
        
        if i + 1 < len(game.move_log):
            black_move = font.render(game.move_log[i+1], True, WHITE)
            log_content.blit(black_move, (150, move_y))
        
        move_y += 30
        move_number += 1
    
    # Draw the log background
    pygame.draw.rect(screen, (50, 50, 50), (log_x - 5, log_y - 5, log_width + 10, log_height + 10))
    
    # Create a clipping area for the log content
    clip_rect = pygame.Rect(log_x, log_y, log_width, log_height)
    old_clip = screen.get_clip()
    screen.set_clip(clip_rect)
    
    # Draw the visible portion of the log content
    screen.blit(log_content, (log_x, log_y - game.log_scroll))
    
    # Reset clipping
    screen.set_clip(old_clip)
    
    # Draw scrollbar if needed
    if log_content_height > log_height:
        scrollbar_width = 10
        scrollbar_x = log_x + log_width - scrollbar_width
        
        # Calculate scrollbar thumb position and size
        thumb_height = max(30, int((log_height / log_content_height) * log_height))
        thumb_position = int((game.log_scroll / (log_content_height - log_height)) * (log_height - thumb_height))
        
        # Draw scrollbar track
        pygame.draw.rect(screen, (70, 70, 70), (scrollbar_x, log_y, scrollbar_width, log_height))
        
        # Draw scrollbar thumb
        pygame.draw.rect(screen, (120, 120, 120), (scrollbar_x, log_y + thumb_position, scrollbar_width, thumb_height))

def draw_game_status(game):
    status_y = HEIGHT - 40
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
    game = ChessGame(player_color='white')
    
    # Create buttons
    export_button = Button(
        BOARD_SIZE + 20, 
        HEIGHT - 50, 
        BUTTON_WIDTH, 
        BUTTON_HEIGHT, 
        "Export Log"
    )
    new_game_button = Button(
        BOARD_SIZE + 20 + BUTTON_WIDTH + 10, 
        HEIGHT - 50, 
        BUTTON_WIDTH, 
        BUTTON_HEIGHT, 
        "New Game"
    )
    
    while True:
        if game.current_turn != game.player_color and not game.promoting_pawn:
            game.make_ai_move()
            
        mouse_pos = pygame.mouse.get_pos()
        export_button.check_hover(mouse_pos)
        new_game_button.check_hover(mouse_pos)
        
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
                
            elif event.type == MOUSEWHEEL:
                if hasattr(game, 'log_scroll'):
                    game.log_scroll -= event.y * 30 
                    log_content_height = max(HEIGHT, (len(game.move_log) // 2 + 2) * 30)
                    game.log_scroll = max(0, min(game.log_scroll, log_content_height - (HEIGHT - 30)))
            
            elif event.type == MOUSEBUTTONDOWN:
                if export_button.is_clicked(mouse_pos, event):
                    game.export_move_log()
                elif new_game_button.is_clicked(mouse_pos, event):
                    game.reset_game()
                elif event.button == 1:  # Left click
                    col = event.pos[0] // SQUARE_SIZE
                    row = event.pos[1] // SQUARE_SIZE
                    if game.current_turn != game.player_color:
                        continue
                    if game.promoting_pawn:
                        promo_row, promo_col = game.promoting_pawn
                        if (col == promo_col and 
                            ((promo_row == 0 and row in [0, 1, 2, 3]) or 
                             (promo_row == 7 and row in [4, 5, 6, 7]))):
                            if promo_row == 0:
                                piece_index = row
                            else:
                                piece_index = 3 - (row - 4)
                            
                            pieces = ['queen', 'rook', 'bishop', 'knight']
                            game.promote_pawn(pieces[piece_index])
                        continue
                    
                    if 0 <= row < 8 and 0 <= col < 8:
                        if not game.selected_piece and game.board[row][col] and game.board[row][col]['color'] == game.current_turn:
                            game.selected_piece = (row, col)
                            game.valid_moves = [(r, c) for r in range(8) for c in range(8)
                                          if game.is_valid_move((row, col), (r, c))]
                            if SOUND_ENABLED:
                                notify_sound.play()
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
        
        screen.fill((0, 0, 0))
        draw_board(game)
        draw_promotion_menu(game)
        draw_move_log(game)
        draw_game_status(game)
        
        # Draw buttons
        export_button.draw(screen)
        new_game_button.draw(screen)
        
        pygame.display.flip()
        clock.tick(60)
if __name__ == "__main__":
    main()