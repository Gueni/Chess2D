# Chess Game Log Analyzer
[![Python](https://img.shields.io/badge/code-Python-3776AB?style=flat&logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-cross--platform-lightgrey)]()

![Chess Analyzer Screenshot](Screenshot.png)

A Python application for analyzing chess game logs with a graphical interface, move navigation, and Stockfish integration for position analysis.

## Features

- Load and parse chess game logs in various formats (SAN, UCI)
- Interactive chess board visualization
- Move-by-move navigation through games
- Highlighting of moves and suggested moves
- Integration with Stockfish engine for position analysis
- Display of move list with SAN notation
- Cross-platform support (Windows, macOS, Linux)

## Requirements

- Python 3.8+
- PyQt6
- python-chess
- Stockfish (optional for analysis)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Gueni/Chess_Game_Log_Analyzer.git
   cd Chess_Game_Log_Analyzer
   ```

2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. (Optional) Download Stockfish from [official website](https://stockfishchess.org/download/) and note the path to the executable.

## Usage

Run the application:
```bash
python chess_analyzer.py
```

### Interface Overview

1. **Chess Board**: Displays the current position with piece symbols
2. **Move List**: Shows all moves in the game with SAN notation
3. **Navigation Controls**:
   - First move (`<<`)
   - Previous move (`<`)
   - Next move (`>`)
   - Last move (`>>`)
4. **Analysis Button**: Analyze current position with Stockfish (if configured)
5. **Status Bar**: Shows current move number and game status

### Loading Games

1. Click "Open Log File" to load a chess game log
2. Supported formats:
   - SAN (Standard Algebraic Notation) - e.g., "1. e4 e5 2. Nf3 Nc6"
   - UCI (Universal Chess Interface) - e.g., "e2e4 e7e5 g1f3 b8c6"
   - Mixed formats with move numbers

### Stockfish Integration

To enable analysis:
1. Download Stockfish for your platform
2. Specify the path to the Stockfish executable in the code:
   ```python
   stockfish_path = "path/to/stockfish/executable"
   ```
3. The "Analyze Position" button will show the best move and evaluation

## Example Log Format

```
Chess Game Move Log
===================

1. e4 e5
2. Nf3 Nc6
3. Bb5 a6
4. Ba4 Nf6
5. O-O Be7
6. Re1 b5
7. Bb3 d6
8. c3 O-O
9. h3 Nb8
10. d4 Nbd7
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.
