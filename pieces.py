import numpy as np
import itertools as itr

from abc import ABC, abstractmethod


PIECE_BLACK = '#000000'
PIECE_WHITE = '#FFFFFF'


class PathIter:
    def __init__(self, step, cond, ret):
        self.step = step
        self.cond = cond
        self.ret = ret

    def walk(self, star, rang=None):
        if not rang:
            rang = itr.count()

        star = np.array(star)

        for k in rang:
            yield self.ret(star, k), star.copy()

            if not self.cond(star, k):
                break

            step = self.step(star, k)
            star += step


class BoardWalk(PathIter):
    def __init__(self, direction):
        self.board = None
        self.piece = None

        direction = np.array(direction)

        def cond(star, k):
            return self.board.is_in_bounds(*(star + direction)) and (k == 0 or not self.board.board[star[0], star[1]].piece)

        def step(star, k):
            return direction

        def ret(star, k):
            return self.piece

        PathIter.__init__(self, step, cond, ret)

    def walk(self, tile, rang=None):
        self.board = tile.board
        self.piece = tile.piece
        yield from PathIter.walk(self, [tile.x, tile.y], rang)


class Piece(ABC):
    SHAPE = "*"
    VALUE = 0

    WHITE = "white"
    BLACK = "black"

    pieces = []
    i = 0

    def __init__(self, board, colour, shape=None, colour_override=None):
        self.board = board
        self.colour = colour
        self.shape = shape or Piece.SHAPE
        self.hash = Piece.i

        if not colour_override:
            colour_override = PIECE_WHITE if colour == Piece.WHITE else PIECE_BLACK

        self.tag = board.create(self, 0, 0, colour=colour_override)
        self.set_state("hidden")

        Piece.i += 1

    @abstractmethod
    def copy(self, colour_override=False):
        ...

    def is_valid_move(self, tile, dx, dy):
        x = tile.x + dx
        y = tile.y + dy

        return any(move[1][0] == x and move[1][1] == y for move in self.moves(tile))

    def path(self, tile, dx, dy):
        yield tile.make_move(dx, dy)

    @abstractmethod
    def see(self, tile):
        ...

    @abstractmethod
    def moves(self, tile):
        ...

#    def __eq__(self, other):
#         if not other:
#             return False
# 
#         return self.colour == other.colour and self.shape == other.shape

    def __hash__(self):
        return self.hash

    def __repr__(self):
        return f"{self.colour} {self.shape} {self.hash}"

    def __str__(self):
        return self.__repr__()

    def set_state(self, state):
        self.board.itemconfigure(self.tag, state=state)
        self.board.tag_raise(self.tag)

    def delete(self):
        self.board.delete(self.tag)
        if self in self.board.pieces[self.colour]:
            self.board.pieces[self.colour].remove(self)

    def can_take(self, dx, dy):
        return True

    def transfer(self, start, end):
        take = self.can_take(end.x - start.x, end.y - start.y)

        target, moved = end.move(self, take)

        if not moved and target:
            start.move(None, True)
        else:
            start.set(None)


class Pawn(Piece):
    SHAPE = "p"
    VALUE = 0

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, Pawn.SHAPE, colour_override)

        self.dy = -1 if self.colour == Piece.WHITE else 1

    def see(self, tile):
        tile.see(self)

        t = tile.offset(-1, self.dy)
        if t:
            t.see(self)

        t = tile.offset(1, self.dy)
        if t:
            t.see(self)

    def moves(self, tile):
        t = tile.offset(0, 2 * self.dy)
        if t and tile.y == 6 if self.dy == -1 else tile.y == 1:
            yield self, (tile.x, tile.y + 2 * self.dy)

        t = tile.offset(0, self.dy)
        if t:
            yield self, (tile.x, tile.y + self.dy)

        t = tile.offset(1, self.dy)
        if t:
            yield self, (tile.x + 1, tile.y + self.dy)

        t = tile.offset(-1, self.dy)
        if t:
            yield self, (tile.x - 1, tile.y + self.dy)

    def copy(self, colour_override=None):
        return Pawn(self.board, self.colour, colour_override=colour_override)

    def can_take(self, dx, dy):
        return dx != 0


class Bishop(Piece):
    SHAPE = "L"
    VALUE = 3

    DIRS = {-1: {-1: BoardWalk([-1, -1]), 1: BoardWalk([-1, 1])}, 1: {-1: BoardWalk([1, -1]), 1: BoardWalk([1, 1])}}

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, Bishop.SHAPE, colour_override)

    def is_valid_move(self, tile, dx, dy):
        return dx == dy or dx == -dy

    def path(self, tile, dx, dy):
        r = max(abs(dx), abs(dy)) + 1

        return Bishop.DIRS[np.sign(dx)][np.sign(dy)].walk(tile, range(r))

    def see(self, tile):
        for a in Bishop.DIRS.values():
            for walker in a.values():
                for p, r in walker.walk(tile):
                    t = tile.board.get_tile(*r)
                    t.see(self)

    def moves(self, tile):
        for a in Bishop.DIRS.values():
            for walker in a.values():
                yield from walker.walk(tile)

    def copy(self, colour_override=False):
        return Bishop(self.board, self.colour, colour_override=colour_override)


class Knight(Piece):
    SHAPE = "P"
    VALUE = 3

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, Knight.SHAPE, colour_override)

    def see(self, tile):
        tile.see(self)

        for move in self.moves(tile):
            t = tile.board.get_tile(*move[1])

            if t:
                t.see(self)

    def moves(self, tile):
        for dx, dy in itr.chain(itr.product([-2, 2], [-1, 1]), itr.product([-1, 1], [-2, 2])):
            yield tile.make_move(dx, dy)

    def copy(self, colour_override=False):
        return Knight(self.board, self.colour, colour_override=colour_override)


class Rook(Piece):
    SHAPE = "T"
    VALUE = 5

    DIRS = {0: {-1: BoardWalk([-1, 0]), 1: BoardWalk([1, 0])}, 1: {-1: BoardWalk([0, -1]), 1: BoardWalk([0, 1])}}  # TODO rooks never walk?

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, Rook.SHAPE, colour_override)

    def is_valid_move(self, tile, dx, dy):
        return dx == 0 or dy == 0

    def path(self, tile, dx, dy):
        y = dx == 0
        s = np.sign(dy) if y else np.sign(dx)
        n = abs(dy) if y else abs(dx)

        return Rook.DIRS[y][s].walk(tile, range(n + 1))

    def moves(self, tile):
        for a in Rook.DIRS.values():
            for b in a.values():
                yield from b.walk(tile)

    def see(self, tile):
        for move in self.moves(tile):
            t = tile.board.get_tile(*move[1])

            if t:
                t.see(self)

    def copy(self, colour_override=False):
        return Rook(self.board, self.colour, colour_override=colour_override)


class Queen(Bishop, Rook):
    SHAPE = "D"
    VALUE = 10

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, Queen.SHAPE, colour_override)

    def is_valid_move(self, tile, dx, dy):
        return Bishop.is_valid_move(self, tile, dx, dy) or Rook.is_valid_move(self, tile, dx, dy)

    def path(self, tile, dx, dy):
        return Bishop.path(self, tile, dx, dy) if Bishop.is_valid_move(self, tile, dx, dy) else Rook.path(self, tile, dx, dy)

    def see(self, tile):
        Bishop.see(self, tile)
        Rook.see(self, tile)

    def moves(self, tile):
        yield from Bishop.moves(self, tile)
        yield from Rook.moves(self, tile)

    def copy(self, colour_override=False):
        return Queen(self.board, self.colour, colour_override=colour_override)


class King(Piece):
    SHAPE = "K"
    VALUE = 0

    def __init__(self, board, colour, colour_override=None):
        Piece.__init__(self, board, colour, King.SHAPE, colour_override)

    def is_valid_move(self, tile, dx, dy):
        return abs(dx) <= 1 and abs(dy) <= 1

    def see(self, tile):
        tile.see(self)

        for move in self.moves(tile):
            t = tile.board.get_tile(*move[1])

            if t:
                t.see(self)

    def moves(self, tile):
        for dx, dy in itr.product([-1, 0, 1], repeat=2):
            if dx or dy:
                yield tile.make_move(dx, dy)

    def copy(self, colour_override=False):
        return King(self.board, self.colour, colour_override=colour_override)


Piece.pieces += [Pawn, Knight, Bishop, Rook, Queen, King]
__all__ = ["Piece", "Pawn", "Knight", "Bishop", "Rook", "Queen", "King"]
