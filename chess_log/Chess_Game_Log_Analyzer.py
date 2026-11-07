import re
import sys
import os
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                            QPushButton, QLabel, QTextEdit, QScrollArea, QFileDialog, QMessageBox)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPainter, QPixmap, QColor, QFont, QIcon
import chess


class ChessBoardWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = chess.Board()
        self.square_size = 80
        self.setMinimumSize(QSize(8 * self.square_size, 8 * self.square_size))
        self.highlighted_squares = set()
        self.last_move = None
        self.piece_images = self.load_piece_images()

    def load_piece_images(self):
        pieces = {}
        piece_types = ['pawn', 'rook', 'knight', 'bishop', 'queen', 'king']
        colors = ['w', 'b']  # Changed to match your file naming convention
        
        # Base directory where the pieces are stored
        pieces_dir = "D:/WORKSPACE/Chess_Game_Log_Analyzer/pieces"
        
        for color in colors:
            for piece_type in piece_types:
                key = f"{color}{piece_type[0]}"  # e.g., 'wp', 'br', etc.
                
                # Construct the filename based on your naming convention
                filename = f"{piece_type}-{color}.svg"
                filepath = os.path.join(pieces_dir, filename)
                
                if os.path.exists(filepath):
                    # Load SVG and scale to square size
                    pixmap = QPixmap(filepath)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(
                            self.square_size, 
                            self.square_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        pieces[key] = pixmap
                    else:
                        print(f"Failed to load {filepath}")
                else:
                    print(f"File not found: {filepath}")
                    
                    # Fallback: create a simple representation
                    pixmap = QPixmap(self.square_size, self.square_size)
                    pixmap.fill(Qt.GlobalColor.transparent)
                    painter = QPainter(pixmap)
                    
                    # Draw a circle with the piece letter
                    bg_color = QColor(240, 217, 181) if color == 'w' else QColor(181, 136, 99)
                    painter.setBrush(bg_color)
                    painter.drawEllipse(10, 10, self.square_size-20, self.square_size-20)
                    
                    # Draw the piece letter
                    font = QFont('Arial', 24)
                    painter.setFont(font)
                    text_color = QColor(0, 0, 0) if color == 'w' else QColor(255, 255, 255)
                    painter.setPen(text_color)
                    
                    letter = piece_type[0].upper() if piece_type != 'knight' else 'N'
                    painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, letter)
                    painter.end()
                    
                    pieces[key] = pixmap
        return pieces

    def paintEvent(self, event):
        painter = QPainter(self)
        
        # Draw the board
        for row in range(8):
            for col in range(8):
                color = QColor(240, 217, 181) if (row + col) % 2 == 0 else QColor(181, 136, 99)
                painter.fillRect(col * self.square_size, row * self.square_size, 
                                self.square_size, self.square_size, color)
        
        # Highlight squares
        for square in self.highlighted_squares:
            row = 7 - (square // 8)
            col = square % 8
            highlight_color = QColor(100, 255, 100, 150)
            painter.fillRect(col * self.square_size, row * self.square_size, 
                            self.square_size, self.square_size, highlight_color)
        
        # Highlight last move
        if self.last_move:
            for square in [self.last_move.from_square, self.last_move.to_square]:
                row = 7 - (square // 8)
                col = square % 8
                move_color = QColor(255, 255, 100, 150)
                painter.fillRect(col * self.square_size, row * self.square_size, 
                                self.square_size, self.square_size, move_color)
        
        # Draw pieces
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece:
                row = 7 - (square // 8)
                col = square % 8
                color_char = 'w' if piece.color == chess.WHITE else 'b'
                piece_char = piece.symbol().lower()
                key = f"{color_char}{piece_char}"
                
                if key in self.piece_images:
                    painter.drawPixmap(col * self.square_size, row * self.square_size, 
                                     self.piece_images[key])
        
        # Draw coordinates
        font = QFont('Arial', 10)
        painter.setFont(font)
        painter.setPen(QColor(120, 120, 120))
        
        # Files (a-h)
        for col in range(8):
            letter = chr(ord('a') + col)
            painter.drawText(col * self.square_size + self.square_size - 15, 
                           8 * self.square_size - 5, letter)
            painter.drawText(col * self.square_size + 5, 15, letter)
        
        # Ranks (1-8)
        for row in range(8):
            number = str(8 - row)
            painter.drawText(5, row * self.square_size + 15, number)
            painter.drawText(8 * self.square_size - 15, 
                           row * self.square_size + self.square_size - 5, number)
        
        painter.end()

    def update_board(self, board, last_move=None, highlighted_squares=None):
        self.board = board
        self.last_move = last_move
        self.highlighted_squares = highlighted_squares or set()
        self.update()

class ChessAnalyzer(QMainWindow):
    def __init__(self, stockfish_path=None):
        super().__init__()
        self.stockfish_path = stockfish_path
        self.board = chess.Board()
        self.moves = []
        self.current_move_index = -1
        self.highlighted_squares = set()
        
        self.init_ui()
        self.setWindowTitle("Chess Game Log Analyzer")
        self.setWindowIcon(QIcon("chess_icon.png"))  # Replace with your icon path
        self.resize(1000, 700)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel with board and controls
        left_panel = QVBoxLayout()
        
        # Chess board
        self.chess_board = ChessBoardWidget()
        left_panel.addWidget(self.chess_board)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Open Log File")
        self.open_button.clicked.connect(self.open_file)
        control_layout.addWidget(self.open_button)
        
        self.first_button = QPushButton("<<")
        self.first_button.clicked.connect(self.first_move)
        self.first_button.setEnabled(False)
        control_layout.addWidget(self.first_button)
        
        self.prev_button = QPushButton("<")
        self.prev_button.clicked.connect(self.prev_move)
        self.prev_button.setEnabled(False)
        control_layout.addWidget(self.prev_button)
        
        self.next_button = QPushButton(">")
        self.next_button.clicked.connect(self.next_move)
        self.next_button.setEnabled(False)
        control_layout.addWidget(self.next_button)
        
        self.last_button = QPushButton(">>")
        self.last_button.clicked.connect(self.last_move)
        self.last_button.setEnabled(False)
        control_layout.addWidget(self.last_button)
        
        self.analyze_button = QPushButton("Analyze Position")
        self.analyze_button.clicked.connect(self.analyze_position)
        self.analyze_button.setEnabled(False)
        control_layout.addWidget(self.analyze_button)
        
        left_panel.addLayout(control_layout)
        
        # Status label
        self.status_label = QLabel("Load a chess game log file to begin")
        left_panel.addWidget(self.status_label)
        
        # Analysis info
        self.analysis_label = QLabel("Analysis will appear here")
        self.analysis_label.setWordWrap(True)
        left_panel.addWidget(self.analysis_label)
        
        main_layout.addLayout(left_panel, stretch=2)
        
        # Right panel with move list
        right_panel = QVBoxLayout()
        
        move_list_label = QLabel("Move List")
        move_list_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_panel.addWidget(move_list_label)
        
        self.move_list = QTextEdit()
        self.move_list.setReadOnly(True)
        self.move_list.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.move_list)
        scroll_area.setWidgetResizable(True)
        right_panel.addWidget(scroll_area)
        
        main_layout.addLayout(right_panel, stretch=1)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Chess Log File", "", "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                self.parse_chess_log(content)
                self.status_label.setText(f"Loaded: {os.path.basename(file_path)} - {len(self.moves)} moves")
                self.update_board()
                self.update_move_list()
                self.enable_controls()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load file: {str(e)}")

    def parse_chess_log(self, content):
        self.moves = []
        self.board.reset()
        self.current_move_index = -1
        
        # Remove header if present
        content = re.sub(r'^Chess Game Move Log.*?\n=+\n', '', content, flags=re.DOTALL)
        
        # Extract moves
        move_lines = content.split('\n')
        for line in move_lines:
            line = line.strip()
            if not line:
                continue
                
            # Split into move pairs (white and black)
            parts = re.split(r'\s+', line)
            if len(parts) >= 2 and '.' in parts[0]:
                # Remove move numbers
                parts = parts[1:]
                
            for move_str in parts:
                if not move_str or '.' in move_str:
                    continue
                
                try:
                    # First try to parse as UCI (e2e4)
                    if len(move_str) == 4 and move_str.isalpha() and move_str.islower():
                        move = chess.Move.from_uci(move_str)
                        if move in self.board.legal_moves:
                            self.moves.append(move)
                            self.board.push(move)
                            continue
                    
                    # Then try to parse as SAN (e4, Nf3, etc.)
                    try:
                        move = self.board.parse_san(move_str)
                        self.moves.append(move)
                        self.board.push(move)
                        continue
                    except chess.IllegalMoveError:
                        pass
                    
                    # Handle castling notation variations
                    if move_str.lower() in ['o-o', '0-0']:
                        move = self.board.parse_san('O-O')
                        self.moves.append(move)
                        self.board.push(move)
                        continue
                    elif move_str.lower() in ['o-o-o', '0-0-0']:
                        move = self.board.parse_san('O-O-O')
                        self.moves.append(move)
                        self.board.push(move)
                        continue
                    
                    # Handle check/checkmate symbols
                    clean_move = re.sub(r'[+#]', '', move_str)
                    if clean_move != move_str:
                        move = self.board.parse_san(clean_move)
                        self.moves.append(move)
                        self.board.push(move)
                        continue
                    
                    print(f"Failed to parse move {move_str}: no matching legal move in {self.board.fen()}")
                except Exception as e:
                    print(f"Failed to parse move {move_str}: {e}")
        
        # Reset board to initial position
        self.board.reset()
        self.current_move_index = -1

    def update_board(self):
        last_move = None
        if 0 <= self.current_move_index < len(self.moves):
            last_move = self.moves[self.current_move_index]
        
        self.chess_board.update_board(
            board=self.board,
            last_move=last_move,
            highlighted_squares=self.highlighted_squares
        )
        
        # Update status
        status = f"Move {self.current_move_index + 1}/{len(self.moves)}"
        if self.board.is_checkmate():
            status += " - Checkmate!"
        elif self.board.is_check():
            status += " - Check"
        elif self.board.is_stalemate():
            status += " - Stalemate"
        self.status_label.setText(status)

    def update_move_list(self):
        self.move_list.clear()
        
        # Replay all moves to generate SAN notation
        temp_board = chess.Board()
        move_number = 1
        move_text = ""
        
        for i, move in enumerate(self.moves):
            try:
                san_move = temp_board.san(move)
                
                if i % 2 == 0:  # White move
                    move_text += f"{move_number}. {san_move}\t"
                else:  # Black move
                    move_text += f"{san_move}\n"
                    move_number += 1
                    
                temp_board.push(move)
            except Exception as e:
                print(f"Error generating SAN for move {move}: {e}")
                # Fall back to UCI notation if SAN fails
                if i % 2 == 0:
                    move_text += f"{move_number}. {move.uci()}\t"
                else:
                    move_text += f"{move.uci()}\n"
                    move_number += 1
        
        self.move_list.setPlainText(move_text)
        
        # Highlight current move
        if 0 <= self.current_move_index < len(self.moves):
            cursor = self.move_list.textCursor()
            move_text = self.move_list.toPlainText()
            
            # Find the position of the current move
            move_num = (self.current_move_index // 2) + 1
            if self.current_move_index % 2 == 0:  # White move
                search_str = f"{move_num}. "
            else:  # Black move
                try:
                    search_str = f"\t{temp_board.san(self.moves[self.current_move_index])}"
                except:
                    search_str = f"\t{self.moves[self.current_move_index].uci()}"
            
            pos = move_text.find(search_str)
            if pos >= 0:
                cursor.setPosition(pos)
                cursor.movePosition(cursor.MoveOperation.Right, cursor.MoveMode.KeepAnchor, len(search_str))
                self.move_list.setTextCursor(cursor)
                self.move_list.ensureCursorVisible()

    def enable_controls(self):
        self.next_button.setEnabled(True)
        self.last_button.setEnabled(True)
        self.prev_button.setEnabled(False)
        self.first_button.setEnabled(False)
        self.analyze_button.setEnabled(bool(self.stockfish_path))

    def first_move(self):
        self.board.reset()
        self.current_move_index = -1
        self.highlighted_squares = set()
        self.update_board()
        self.update_move_list()
        self.update_nav_buttons()

    def prev_move(self):
        if self.current_move_index >= 0:
            self.board.pop()
            self.current_move_index -= 1
            self.highlighted_squares = set()
            self.update_board()
            self.update_move_list()
            self.update_nav_buttons()

    def next_move(self):
        if self.current_move_index < len(self.moves) - 1:
            self.current_move_index += 1
            move = self.moves[self.current_move_index]
            self.board.push(move)
            self.highlighted_squares = set()
            self.update_board()
            self.update_move_list()
            self.update_nav_buttons()

    def last_move(self):
        while self.current_move_index < len(self.moves) - 1:
            self.next_move()

    def update_nav_buttons(self):
        self.first_button.setEnabled(self.current_move_index > -1)
        self.prev_button.setEnabled(self.current_move_index > -1)
        self.next_button.setEnabled(self.current_move_index < len(self.moves) - 1)
        self.last_button.setEnabled(self.current_move_index < len(self.moves) - 1)

    def analyze_position(self):
        if not self.stockfish_path or not os.path.exists(self.stockfish_path):
            QMessageBox.critical(self, "Error", "Stockfish engine not found at the specified path")
            return
        
        try:
            # Initialize Stockfish
            stockfish = subprocess.Popen(
                self.stockfish_path,
                universal_newlines=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Send position to Stockfish
            stockfish.stdin.write(f"position fen {self.board.fen()}\n")
            stockfish.stdin.write("go depth 15\n")
            stockfish.stdin.flush()
            
            # Read analysis
            output = []
            while True:
                line = stockfish.stdout.readline()
                if not line or "bestmove" in line:
                    break
                if "info" in line and "score" in line:
                    output.append(line.strip())
            
            # Get the last info line (most complete evaluation)
            if output:
                last_line = output[-1]
                
                # Parse evaluation
                cp_match = re.search(r"cp (-?\d+)", last_line)
                mate_match = re.search(r"mate (-?\d+)", last_line)
                
                if mate_match:
                    eval_text = f"Mate in {mate_match.group(1)}"
                elif cp_match:
                    cp = int(cp_match.group(1))
                    eval_text = f"{cp/100:.1f} pawns ({'White' if cp > 0 else 'Black'} advantage)"
                else:
                    eval_text = "Evaluation not found"
                
                # Parse best move
                best_move_match = re.search(r"pv (\w+)", last_line)
                if best_move_match:
                    try:
                        move = self.board.parse_uci(best_move_match.group(1))
                        eval_text += f"\nBest move: {self.board.san(move) if move in self.board.legal_moves else move.uci()}"
                        
                        # Highlight squares for best move
                        self.highlighted_squares = {move.from_square, move.to_square}
                        self.update_board()
                    except Exception as e:
                        print(f"Error parsing best move: {e}")
                
                self.analysis_label.setText(eval_text)
            
            stockfish.terminate()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to analyze position: {str(e)}")

def main():
    app = QApplication(sys.argv)
    
    # Replace with your actual Stockfish path or None if not available
    stockfish_path = "D:/WORKSPACE/Chess2D/stockfish/stockfish-windows-x86-64-avx2.exe"
    
    # Check if Stockfish exists
    if not os.path.exists(stockfish_path):
        stockfish_path = None
        print("Stockfish engine not found at the specified path. Analysis will be disabled.")
    
    analyzer = ChessAnalyzer(stockfish_path)
    analyzer.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()