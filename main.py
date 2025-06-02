import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np

pygame.init()
width, height = 1000, 600  # Wider to include terminal panel
pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)

gluPerspective(45, (width / height), 0.1, 50.0)
glTranslatef(0.0, -1.0, -10.0)
glRotatef(20, 1, 0, 0)

LIGHT_SQUARE = (0.9, 0.9, 0.7)
DARK_SQUARE = (0.5, 0.3, 0.1)
WHITE_PIECE = (0.9, 0.9, 0.9)
BLACK_PIECE = (0.2, 0.2, 0.2)
HIGHLIGHT = (0.8, 0.8, 0.0, 0.5)

square_labels = "abcdefgh"

class ChessGame:
    def __init__(self):
        self.board = self.initialize_board()
        self.selected_piece = None
        self.current_turn = 'white'
        self.valid_moves = []
        self.game_over = False
        self.winner = None
        self.move_log = []

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
        return f"{square_labels[col]}{8 - row}"

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
                if ((start[0] == 6 and piece['color'] == 'white') or (start[0] == 1 and piece['color'] == 'black')) and \
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

def draw_cube(color, size=1.0):
    vertices = [[size, -size, -size], [size, size, -size], [-size, size, -size], [-size, -size, -size],
                [size, -size, size], [size, size, size], [-size, -size, size], [-size, size, size]]
    faces = [(0, 1, 2, 3), (4, 5, 7, 6), (0, 4, 6, 3), (1, 5, 7, 2), (0, 1, 5, 4), (3, 2, 7, 6)]
    glBegin(GL_QUADS)
    glColor3fv(color)
    for face in faces:
        for vertex in face:
            glVertex3fv(vertices[vertex])
    glEnd()

def draw_cylinder(color, radius, height, sides=32):
    glColor3fv(color)
    glBegin(GL_POLYGON)
    for i in range(sides):
        angle = 2 * np.pi * i / sides
        glVertex3f(radius * np.cos(angle), height / 2, radius * np.sin(angle))
    glEnd()
    glBegin(GL_POLYGON)
    for i in range(sides):
        angle = 2 * np.pi * i / sides
        glVertex3f(radius * np.cos(angle), -height / 2, radius * np.sin(angle))
    glEnd()
    glBegin(GL_QUAD_STRIP)
    for i in range(sides + 1):
        angle = 2 * np.pi * i / sides
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        glVertex3f(x, height / 2, y)
        glVertex3f(x, -height / 2, y)
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
            glPushMatrix()
            glTranslatef(col - 3.5, 0, row - 3.5)
            draw_cube(LIGHT_SQUARE if (row + col) % 2 == 0 else DARK_SQUARE, 0.5)
            if game.selected_piece == (row, col):
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4fv(HIGHLIGHT)
                draw_cube((1, 1, 1), 0.51)
                glDisable(GL_BLEND)
            if (row, col) in game.valid_moves:
                glEnable(GL_BLEND)
                glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
                glColor4f(0, 1, 0, 0.3)
                draw_cube((1, 1, 1), 0.51)
                glDisable(GL_BLEND)
            glPopMatrix()
            piece = game.board[row][col]
            if piece:
                draw_piece(piece['type'], piece['color'], col - 3.5, row - 3.5)

def draw_terminal_log(move_log):
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, width, 0, height)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    font = pygame.font.SysFont('Consolas', 16)
    start_y = height - 30
    for i, line in enumerate(reversed(move_log[-20:])):
        text = font.render(line, True, (255, 255, 255))
        text_data = pygame.image.tostring(text, "RGBA", True)
        glWindowPos2d(810, start_y - i * 20)
        glDrawPixels(text.get_width(), text.get_height(), GL_RGBA, GL_UNSIGNED_BYTE, text_data)

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)

def get_board_position(mouse_pos, viewport, modelview, projection):
    x, y = mouse_pos
    y = height - y
    depth = glReadPixels(x, y, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)
    if depth[0][0] == 1.0:
        return None
    world_coords = gluUnProject(x, y, depth[0][0], modelview, projection, viewport)
    board_x = round(world_coords[0] + 3.5)
    board_z = round(world_coords[2] + 3.5)
    if 0 <= board_x < 8 and 0 <= board_z < 8:
        return (int(board_z), int(board_x))
    return None

def main():
    glEnable(GL_DEPTH_TEST)
    game = ChessGame()
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == QUIT:
                running = False
            elif event.type == MOUSEBUTTONDOWN and event.button == 1:
                viewport = glGetIntegerv(GL_VIEWPORT)
                modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
                projection = glGetDoublev(GL_PROJECTION_MATRIX)
                pos = get_board_position(event.pos, viewport, modelview, projection)
                if pos:
                    row, col = pos
                    if not game.selected_piece and game.board[row][col] and game.board[row][col]['color'] == game.current_turn:
                        game.selected_piece = (row, col)
                        game.valid_moves = [(r, c) for r in range(8) for c in range(8)
                                            if game.is_valid_move((row, col), (r, c))]
                    elif game.selected_piece:
                        if pos in game.valid_moves:
                            game.move_piece(game.selected_piece, pos)
                        game.selected_piece = None
                        game.valid_moves = []
            elif event.type == KEYDOWN:
                if event.key == K_LEFT:
                    glRotatef(5, 0, 1, 0)
                elif event.key == K_RIGHT:
                    glRotatef(-5, 0, 1, 0)
                elif event.key == K_UP:
                    glRotatef(5, 1, 0, 0)
                elif event.key == K_DOWN:
                    glRotatef(-5, 1, 0, 0)
                elif event.key == K_EQUALS or event.key == K_PLUS:
                    glTranslatef(0, 0, 0.5)
                elif event.key == K_MINUS:
                    glTranslatef(0, 0, -0.5)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        draw_board(game)
        draw_terminal_log(game.move_log)
        pygame.display.flip()
        clock.tick(60)
    pygame.quit()

if __name__ == "__main__":
    main()
