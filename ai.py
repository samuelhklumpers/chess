import bisect

from chess import *


class FrozenTile:
    seen = []

    def __init__(self, x, y, board):
        self.x = x
        self.y = y
        self.board = board

        self.type = None
        self.piece = None

    def load(self, piece, typ):
        self.piece = piece
        self.type = typ

    def see(self, by: Piece):
        self.seen += [(self.piece, self.type)]

    def make_move(self, dx, dy):
        return self.piece, (self.x + dx, self.y + dy)

    def move(self, piece: Piece):
        self.piece = piece
        self.type = 

    def set(self, piece):
        self.piece = piece
        self.place_on_screen(piece)

    def offset(self, dx, dy):
        return self.board.get_tile(self.x + dx, self.y + dy)

    def set_state(self, colour, state):
        if state == "hidden":
            self.board.itemconfigure(self.canvas_id, fill=TILE_UNSEEN_WHITE if self.colour == "white" else TILE_UNSEEN_BLACK)

        p = self.piece
        if p:
            if p.colour == colour:
                p.set_state(state)

                if state == "normal":
                    self.board.tag_raise(p.tag)

        m = self.memory[colour]
        if m and self.do_memory:
            m.set_state(state)

            if state == "normal":
                self.board.tag_raise(m.tag)

    def place_on_screen(self, piece):
        if piece:
            self.board.coords(piece.tag, self.board.screen_coord(self.x, self.y, True))

    def valid(self, dx, dy):
        return self.piece and self.piece.is_valid_move(self, dx, dy)

def covering_score(pieces, board, seen, colour):
    # don't cheat!
    covering = {}

    for piece in itr.chain(pieces, seen):
        covering[piece] = 0

    for t in board.flat:
        if t.memory[colour] and not t.piece in seen:
            covering[t.memory[colour]] = 0

    for piece in covering:
        seen = piece.vision()

        covering[seen] += 1 if piece.colour == seen.colour else -1

    scores = {"black": 0, "white": 0}

    for piece, coverage in covering.items():
        scores[piece.colour] += rate_cover(piece, coverage)

    return scores


def rate_cover(piece, coverage):
    if isinstance(piece, King):
        return -1000 if coverage < 0 else 0
    else:
        return piece.value * coverage


class SubMax:
    def __init__(self, f, n):
        self.scores = []
        self.items = []
        self.n = n
        self.f = f

    def add(self, item):
        score = self.f(item)

        i = bisect.bisect_left(self.scores, score)
        if i < self.n:
            self.scores.insert(i, score)
            self.items.insert(i, item)

            if len(self.scores) > self.n:
                del self.scores[-1]
                del self.items[-1]


def do_move(board, piece, x, y):
    piece.x, old_x = x, piece.x
    piece.x, old_y = y, piece.y

    board[x, y].piece, old_piece = piece, board[x, y].piece
    board[old_x, old_y].piece = None
    piece.x, piece.y = x, y
    board.pieces[old_piece.colour].remove(old_piece)

    return old_piece, old_x, old_y


def undo_move(board, piece, x, y, old_piece, old_x, old_y):
    board[x, y].piece = old_piece
    board[old_x, old_y] = piece
    piece.x, piece.y = old_x, old_y
    board.pieces[old_piece.colour].append(old_piece)


def ai(board, colour, depth, width):
    def f(move):
        piece, x, y = move

        old_piece, old_x, old_y = do_move(board, piece, x, y)

        score = covering_score(board)
        score = score[colour] - sum(score[c] for c in score if c != colour)

        undo_move(board, piece, x, y, old_piece, old_x, old_y)

        return score

    if depth == 0:
        width = 1

    submax = SubMax(f, width)

    for piece in board.pieces[colour]:
        for x, y in piece.moves():
            submax.add((piece, x, y))

    if depth > 0:
        score_m = -1e10
        move_m = ()
        for move in submax.items:
            undo = do_move(board, *move)

            score, move2 = ai(board, colour, depth - 1, width)

            undo_move(board, *move, *undo)

            if score > score_m:
                score_m = score
                move_m = move2

        return score_m, (move, move_m)
    else:
        return submax.scores[0], (submax.items[0], None)
