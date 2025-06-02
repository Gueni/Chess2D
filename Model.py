from enum import Enum

class Game:
  """A chess game with game state information."""

  def __init__(self, positions=None):
    """Create a new game with default starting positions."""
    if positions is None:
      self._positions = self._init_positions()
    else:
      self._position = positions

    # true if white's turn
    self.turn = True
    self.playing = True
    self.focused = None

  def is_playing(self):
    return self.playing

  def move(self, rank, file):
    print(rank, file)
    return self.focused.move(Position(rank, file))

  def get_focused(self):
    return self.focused

  def get_focused_position(self):
    return self.focused.get_position().get_rank(), self.focused.get_position().get_file()

  def get_model(self):
    return self.focused.get_model_idx()

  def set_focused(self, position):
      for piece in self._positions:
          if piece.get_position().get_rank() == position[0] and piece.get_position().get_file() == position[1]:
              self.focused = piece 
              return

  def unfocus(self):
    self.focused = None

  def _init_positions(self):
    """Default starting positions."""
    result = []
    for file in range(8):
      result.append(Pawn(Position(7-file, 1), Colour.BLACK, False, "blackPawnModels", file))
      result.append(Pawn(Position(7-file, 6), Colour.WHITE, False, "whitePawnModels", file))

    result.append(Rook(Position(0, 0), Colour.BLACK, "blackRookModels", 0))
    result.append(Rook(Position(7, 0), Colour.BLACK, "blackRookModels", 1))
    result.append(Rook(Position(0, 7), Colour.WHITE, "whiteRookModels", 0))
    result.append(Rook(Position(7, 7), Colour.WHITE, "whiteRookModels", 1))

    result.append(Knight(Position(1, 0), Colour.BLACK, "blackKnightModels", 0))
    result.append(Knight(Position(6, 0), Colour.BLACK, "blackKnightModels", 1))
    result.append(Knight(Position(1, 7), Colour.WHITE, "whiteKnightModels", 0))
    result.append(Knight(Position(6, 7), Colour.WHITE, "whiteKnightModels",1))

    result.append(Bishop(Position(2, 0), Colour.BLACK, "blackBishopModels", 0))
    result.append(Bishop(Position(5, 0), Colour.BLACK, "blackBishopModels", 1))
    result.append(Bishop(Position(2, 7), Colour.WHITE, "whiteBishopModels", 0))
    result.append(Bishop(Position(5, 7), Colour.WHITE, "whiteBishopModels",1))

    result.append(Queen(Position(3, 0), Colour.BLACK, "blackQueenModel"))
    result.append(Queen(Position(3, 7), Colour.WHITE, "whiteQueenModel"))

    result.append(King(Position(4, 0), Colour.BLACK, "blackKingModel"))
    result.append(King(Position(4, 7), Colour.WHITE, "whiteKingModel"))

    return result

class Position:
  """Represent a position on the board."""
  def __init__(self, rank, file):
    """Create a new position with the given rank and file."""
    self._rank = rank
    self._file = file

  def get_rank(self):
    """Return this position's rank."""
    return self._rank

  def get_file(self):
    """Return this position's file."""
    return self._file

class Piece:
  """Represent a piece on the board."""
  def __init__(self, position, colour, model, idx=None):
    """Initialise a new piece with the given position."""
    self._position = position
    self._colour = colour
    self._model = model
    self._idx = idx

  def get_model_idx(self):
      return self._model, self._idx

  def get_position(self):
    return self._position

  def move(self, position: Position):
    """(Abstract) move the piece to the new position.
    Parameters:
      position:  the position to move to

    Return True if a valid move and False otherwise.
    """
    pass

class Pawn(Piece):
  """A pawn piece."""
  def __init__(self, position: Position, colour, en_passant: bool, model, idx):
    """Initialise a new pawn piece."""
    super().__init__(position, colour, model, idx)
    self._en_passant = en_passant

  def move(self, position):
    # Check the given move is valid
    mult = 1 if self._colour == Colour.WHITE else -1
    if mult * (self._position.get_file() - position.get_file()) not in [1, 2]:
      return False # too far vertically
    # TODO
    self._position = position 
    return True

class Rook(Piece):
  pass

class Knight(Piece):
  pass

class Bishop(Piece):
  pass

class Queen(Piece):
  pass

class King(Piece):
  pass

class Colour(Enum):
  WHITE = 0
  BLACK = 1

