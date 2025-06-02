import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np

# Initialize pygame
pygame.init()
width, height = 1000, 600  # Increased width to accommodate move history
pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)

# Set up OpenGL perspective
gluPerspective(45, (800 / height), 0.1, 50.0)  # Adjusted for chess board area
glTranslatef(0.0, -1.0, -10.0)
glRotatef(20, 1, 0, 0)

# Colors
LIGHT_SQUARE = (0.9, 0.9, 0.7)
DARK_SQUARE = (0.5, 0.3, 0.1)
WHITE_PIECE = (0.9, 0.9, 0.9)
BLACK_PIECE = (0.2, 0.2, 0.2)
HIGHLIGHT = (0.8, 0.8, 0.0, 0.5)
MOVE_HISTORY_BG = (0.1, 0.1, 0.1, 0.7)
TEXT_COLOR = (255, 255, 255)

class ChessGame:
    def __init__(self):
        self.board = self.initialize_board()
        self.selected_piece = None
        self.current_turn = 'white'
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.move_history = []
    
    def initialize_board(self):
        # Create an 8x8 chess board with initial piece positions
        board = [[None for _ in range(8)] for _ in range(8)]
        
        # Place pawns
        for col in range(8):
            board[1][col] = {'type': 'pawn', 'color': 'black'}
            board[6][col] = {'type': 'pawn', 'color': 'white'}
        
        # Place other pieces
        pieces = ['rook', 'knight', 'bishop', 'queen', 'king', 'bishop', 'knight', 'rook']
        for col, piece in enumerate(pieces):
            board[0][col] = {'type': piece, 'color': 'black'}
            board[7][col] = {'type': piece, 'color': 'white'}
        
        return board
    
    def is_valid_move(self, start_pos, end_pos):
        # Simplified move validation (would need to be expanded for full chess rules)
        piece = self.board[start_pos[0]][start_pos[1]]
        if not piece:
            return False
        
        # Check if it's the correct color's turn
        if piece['color'] != self.current_turn:
            return False
        
        # Check if destination is occupied by same color
        target = self.board[end_pos[0]][end_pos[1]]
        if target and target['color'] == piece['color']:
            return False
        
        # Basic movement patterns (simplified)
        row_diff = abs(end_pos[0] - start_pos[0])
        col_diff = abs(end_pos[1] - start_pos[1])
        
        if piece['type'] == 'pawn':
            direction = 1 if piece['color'] == 'white' else -1
            # Basic forward move
            if start_pos[1] == end_pos[1]:
                if end_pos[0] == start_pos[0] + direction and not target:
                    return True
                # Double move from starting position
                if ((start_pos[0] == 6 and piece['color'] == 'white') or 
                    (start_pos[0] == 1 and piece['color'] == 'black')):
                    if end_pos[0] == start_pos[0] + 2 * direction and not target:
                        return True
            # Capture
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
            return (row_diff == 0 or col_diff == 0) or (row_diff == col_diff)
        
        elif piece['type'] == 'king':
            return row_diff <= 1 and col_diff <= 1
        
        return False
    
    def move_piece(self, start_pos, end_pos):
            if self.is_valid_move(start_pos, end_pos):
                start_row, start_col = start_pos
                end_row, end_col = end_pos
                piece = self.board[start_row][start_col]
                
                # Record the move
                piece_type = piece['type']
                if piece_type != 'pawn':
                    piece_type = piece_type[0].upper()  # K, Q, R, B, N
                else:
                    piece_type = ''
                
                # Convert to algebraic notation
                col_letter = chr(ord('a') + start_col)
                move_text = f"{piece_type}{col_letter}{8-start_row}"
                
                # Check if it's a capture
                if self.board[end_row][end_col]:
                    move_text += 'x'
                
                # Add destination
                dest_col = chr(ord('a') + end_col)
                move_text += f"{dest_col}{8-end_row}"
                
                # Add to move history
                if self.current_turn == 'white':
                    self.move_history.append(f"{len(self.move_history)//2 + 1}. {move_text}")
                else:
                    if len(self.move_history) % 2 == 1:  # White has moved, black is moving
                        self.move_history[-1] += f" {move_text}"
                    else:
                        self.move_history.append(f"   {move_text}")
                
                # Check if this is a capture (for game over condition)
                target = self.board[end_row][end_col]
                if target and target['type'] == 'king':
                    self.game_over = True
                    self.winner = self.current_turn
                
                # Move the piece
                self.board[end_row][end_col] = piece
                self.board[start_row][start_col] = None
                
                # Switch turns
                self.current_turn = 'black' if self.current_turn == 'white' else 'white'
                return True
            return False

# 3D Rendering functions
def draw_cube(color, size=1.0):
    vertices = [
        [size, -size, -size],
        [size, size, -size],
        [-size, size, -size],
        [-size, -size, -size],
        [size, -size, size],
        [size, size, size],
        [-size, -size, size],
        [-size, size, size]
    ]
    
    edges = [
        (0, 1, 2, 3),
        (4, 5, 7, 6),
        (0, 4, 6, 3),
        (1, 5, 7, 2),
        (0, 1, 5, 4),
        (3, 2, 7, 6)
    ]
    
    glBegin(GL_QUADS)
    glColor3fv(color)
    for edge in edges:
        for vertex in edge:
            glVertex3fv(vertices[vertex])
    glEnd()

def draw_cylinder(color, radius, height, sides=32):
    glColor3fv(color)
    
    # Draw the top and bottom
    glBegin(GL_POLYGON)
    for i in range(sides):
        angle = 2 * np.pi * i / sides
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        glVertex3f(x, height/2, y)
    glEnd()
    
    glBegin(GL_POLYGON)
    for i in range(sides):
        angle = 2 * np.pi * i / sides
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        glVertex3f(x, -height/2, y)
    glEnd()
    
    # Draw the sides
    glBegin(GL_QUAD_STRIP)
    for i in range(sides + 1):
        angle = 2 * np.pi * i / sides
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        glVertex3f(x, height/2, y)
        glVertex3f(x, -height/2, y)
    glEnd()

def draw_piece(piece_type, color, x, z):
    piece_color = WHITE_PIECE if color == 'white' else BLACK_PIECE
    
    glPushMatrix()
    glTranslatef(x, 0.6, z)
    
    if piece_type == 'pawn':
        draw_cylinder(piece_color, 0.3, 0.6)
        glTranslatef(0, 0.3, 0)
        draw_cylinder(piece_color, 0.2, 0.3)
    
    elif piece_type == 'rook':
        draw_cube(piece_color, 0.3)
        glTranslatef(0, 0.3, 0)
        draw_cube(piece_color, 0.2)
    
    elif piece_type == 'knight':
        draw_cylinder(piece_color, 0.3, 0.4)
        glTranslatef(0, 0.2, 0.2)
        draw_cube(piece_color, 0.2)
    
    elif piece_type == 'bishop':
        draw_cylinder(piece_color, 0.3, 0.6)
        glTranslatef(0, 0.3, 0)
        draw_cylinder(piece_color, 0.15, 0.3)
    
    elif piece_type == 'queen':
        draw_cylinder(piece_color, 0.3, 0.6)
        glTranslatef(0, 0.3, 0)
        draw_cylinder(piece_color, 0.2, 0.3)
        glTranslatef(0, 0.15, 0)
        draw_cylinder(piece_color, 0.1, 0.3)
    
    elif piece_type == 'king':
        draw_cylinder(piece_color, 0.3, 0.6)
        glTranslatef(0, 0.3, 0)
        draw_cylinder(piece_color, 0.2, 0.3)
        glTranslatef(0, 0.15, 0)
        draw_cube(piece_color, 0.15)
    
    glPopMatrix()

def draw_board(game):
    for row in range(8):
        for col in range(8):
            # Draw square
            glPushMatrix()
            glTranslatef(col - 3.5, 0, row - 3.5)
            
            # Alternate square colors
            if (row + col) % 2 == 0:
                draw_cube(LIGHT_SQUARE, 0.5)
            else:
                draw_cube(DARK_SQUARE, 0.5)
            
            # Highlight selected square
            if game.selected_piece and game.selected_piece == (row, col):
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4fv(HIGHLIGHT)
                draw_cube((1, 1, 1), 0.51)  # Slightly larger cube for highlight
                glDisable(GL_BLEND)
            
            # Highlight valid moves
            if (row, col) in game.valid_moves:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4f(0, 1, 0, 0.3)
                draw_cube((1, 1, 1), 0.51)
                glDisable(GL_BLEND)
            
            glPopMatrix()
            
            # Draw piece
            piece = game.board[row][col]
            if piece:
                draw_piece(piece['type'], piece['color'], col - 3.5, row - 3.5)

def draw_game_over(winner):
    # Switch to 2D orthographic projection for text
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, width, 0, height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    
    # Draw semi-transparent background
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(0, 0, 0, 0.7)
    glBegin(GL_QUADS)
    glVertex2f(width * 0.25, height * 0.4)
    glVertex2f(width * 0.75, height * 0.4)
    glVertex2f(width * 0.75, height * 0.6)
    glVertex2f(width * 0.25, height * 0.6)
    glEnd()
    glDisable(GL_BLEND)
    
    # Draw text
    font = pygame.font.SysFont('Arial', 40)
    text = font.render(f"{winner.capitalize()} wins!", True, (255, 255, 255))
    text_data = pygame.image.tostring(text, "RGBA", True)
    
    glRasterPos2f(width // 2 - text.get_width() // 2, height // 2 - text.get_height() // 2)
    glDrawPixels(text.get_width(), text.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)
    
    # Restore 3D projection
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def get_board_position(mouse_pos, viewport, modelview, projection):
    # Convert mouse position to 3D world coordinates
    x, y = mouse_pos
    y = height - y  # Invert y coordinate
    
    # Get depth buffer value at mouse position
    depth = glReadPixels(x, y, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)
    
    if depth[0][0] == 1.0:  # No object clicked
        return None
    
    # Unproject to get world coordinates
    world_coords = gluUnProject(x, y, depth[0][0], modelview, projection, viewport)
    
    # Convert to board coordinates
    board_x = round(world_coords[0] + 3.5)
    board_z = round(world_coords[2] + 3.5)
    
    # Check if coordinates are within board bounds
    if 0 <= board_x < 8 and 0 <= board_z < 8:
        return (int(board_z), int(board_x))
    return None

# Main game loop
def main():
    game = ChessGame()
    clock = pygame.time.Clock()
    running = True
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                # Get viewport and matrices for unprojection
                viewport = glGetIntegerv(GL_VIEWPORT)
                modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
                projection = glGetDoublev(GL_PROJECTION_MATRIX)
                
                # Get board position from mouse click
                pos = get_board_position(event.pos, viewport, modelview, projection)
                
                if pos:
                    row, col = pos
                    # If no piece selected and clicked square has a piece of current turn's color
                    if not game.selected_piece and game.board[row][col] and game.board[row][col]['color'] == game.current_turn:
                        game.selected_piece = (row, col)
                        # Generate valid moves (simplified - would need proper move generation)
                        game.valid_moves = []
                        for r in range(8):
                            for c in range(8):
                                if game.is_valid_move((row, col), (r, c)):
                                    game.valid_moves.append((r, c))
                    
                    # If a piece is already selected
                    elif game.selected_piece:
                        # If clicked on a valid move square, move the piece
                        if pos in game.valid_moves:
                            game.move_piece(game.selected_piece, pos)
                        
                        # Reset selection
                        game.selected_piece = None
                        game.valid_moves = []
            
            elif event.type == pygame.KEYDOWN:
                # Rotate view with arrow keys
                if event.key == pygame.K_LEFT:
                    glRotatef(5, 0, 1, 0)
                elif event.key == pygame.K_RIGHT:
                    glRotatef(-5, 0, 1, 0)
                elif event.key == pygame.K_UP:
                    glRotatef(5, 1, 0, 0)
                elif event.key == pygame.K_DOWN:
                    glRotatef(-5, 1, 0, 0)
                # Zoom with + and -
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    glTranslatef(0, 0, 0.5)
                elif event.key == pygame.K_CAPSLOCK:
                    glTranslatef(0, 0, -0.5)
        
        # Clear screen
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # Draw the board and pieces
        draw_board(game)
        
        # Draw game over message if applicable
        if game.game_over:
            draw_game_over(game.winner)
        
        pygame.display.flip()
        clock.tick(60)
    
    pygame.quit()

if __name__ == "__main__":
    # Enable depth testing for 3D
    glEnable(GL_DEPTH_TEST)
    main()