# Chess 2D
[![Python](https://img.shields.io/badge/code-Python-3776AB?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Platform](https://img.shields.io/badge/platform-cross--platform-lightgrey)]()
[![Made with](https://img.shields.io/badge/made%20with-love-red)]()

<div align="center">
  <img src="chess.ico" alt="Chess Icon" width="100"/>
  <h1>♔ Chess 2D ♚</h1>

</div>

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

## ToDo
 - Added scroll functionality for move history console
 - Implemented look menu in console UI
 - Fixed various button interaction bugs
 - Improved pawn promotion menu stability
 - Enhanced move validation edge cases