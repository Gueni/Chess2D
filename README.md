# Chess 2D

A classic chess game implementation in Python using Pygame with all standard chess rules and move validation.

![Chess 2D Screenshot](Screenshot.png)

## Features

- Complete chess rules implementation:
  - All piece movements (including en passant and castling)
  - Check/checkmate detection
  - Pawn promotion
  - Move validation
- Clean graphical interface with:
  - Chess board with coordinates
  - Move highlighting
  - Move history log
  - Game status display
- Fallback graphics when piece images aren't available
- PyInstaller compatible resource loading

## Requirements

- Python 3.6+
- Pygame

## Installation

1. Clone the repository:
```bash
git clone https://github.com/gueni/Chess2D.git
cd Chess2D
```

## How to Play

- Left-click on a piece to select it (valid moves will be highlighted)

- Click on a highlighted square to move the selected piece

- When promoting a pawn, click on the desired piece type

- Press ESC to cancel selection

## Controls
 - Mouse: Select and move pieces

 - ESC: Cancel current selection

