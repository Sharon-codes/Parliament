class Board:
    def __init__(self):
        self.squares = [[None]*8 for _ in range(8)]
        self.initialize_board()

    def initialize_board(self):
        # Initialize the board with the standard setup
        for i in range(8):
            self.squares[1][i] = Pawn('white')
            self.squares[6][i] = Pawn('black')
        self.squares[0][0] = Rook('white')
        self.squares[0][7] = Rook('white')
        self.squares[0][1] = Knight('white')
        self.squares[0][6] = Knight('white')
        self.squares[0][2] = Bishop('white')
        self.squares[0][5] = Bishop('white')
        self.squares[0][3] = Queen('white')
        self.squares[0][4] = King('white')
        self.squares[7][0] = Rook('black')
        self.squares[7][7] = Rook('black')
        self.squares[7][1] = Knight('black')
        self.squares[7][6] = Knight('black')
        self.squares[7][2] = Bishop('black')
        self.squares[7][5] = Bishop('black')
        self.squares[7][3] = Queen('black')
        self.squares[7][4] = King('black')

    def print_board(self):
        # Print the board
        for i in range(8):
            for j in range(8):
                if self.squares[i][j] is not None:
                    print(self.squares[i][j].symbol, end=' ')
                else:
                    print('-', end=' ')
            print()

class Piece:
    def __init__(self, color):
        self.color = color

    def symbol(self):
        # Return the symbol of the piece
        pass

class Pawn(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'P' if self.color == 'white' else 'p'

class Rook(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'R' if self.color == 'white' else 'r'

class Knight(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'N' if self.color == 'white' else 'n'

class Bishop(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'B' if self.color == 'white' else 'b'

class Queen(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'Q' if self.color == 'white' else 'q'

class King(Piece):
    def __init__(self, color):
        super().__init__(color)

    def symbol(self):
        return 'K' if self.color == 'white' else 'k'

class Game:
    def __init__(self):
        self.board = Board()
        self.current_player = 'white'

    def play(self):
        while True:
            self.board.print_board()
            move = input("Enter move (e.g., e2-e4): ")
            # Parse the move and update the board
            # Check if the move is valid
            # Switch the current player

game = Game()
game.play()
