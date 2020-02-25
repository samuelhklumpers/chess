import socket
import time
import threading

import tkinter as tk
import numpy as np
import itertools as itr

from pieces import *
from tkinter import font
from transit_client import transit


COLOURS = [Piece.BLACK, Piece.WHITE]

TILE_BLACK = '#AF8521'
TILE_WHITE = '#E2DA9C'

TILE_UNSEEN_BLACK = '#6B5114'
TILE_UNSEEN_WHITE = '#87825E'

MEMORY_COLOUR = '#444444'

REL_PIECE_SIZE = 0.75

window = tk.Tk("chess")
window.geometry("560x560")


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx
    args = [iter(iterable)] * n
    return itr.zip_longest(fillvalue=fillvalue, *args)


class Tile:
    def __init__(self, x, y, board):
        self.x = x
        self.y = y
        self.board = board
        self.canvas_id = None

        self.piece = None
        self.do_memory = True

        self.memory = {c: None for c in COLOURS}
        self.taken = {c: None for c in COLOURS}

        p = (self.x + self.y + 1) % 2
        self.colour = "white" if p else "black"

    def toggle_memory(self):
        self.do_memory = not self.do_memory

    def draw(self, on, dx, dy):
        a, b = on.screen_coord(self.x, self.y)

        c = TILE_WHITE if self.colour == "white" else TILE_BLACK

        self.canvas_id = on.create_rectangle(a, b, a + dx, b + dy, fill=c)

    def load(self, piece):
        self.memory[Piece.WHITE if piece.colour == Piece.BLACK else Piece.BLACK] = m = piece.copy(MEMORY_COLOUR)
        self.set(piece)
        self.place_on_screen(m)

    def see(self, by: Piece):
        """
        Register this tile in the vision of by.

        :param by: the seeing piece
        :return: the seen piece
        """

        self.board.itemconfigure(self.canvas_id, fill=TILE_WHITE if self.colour == "white" else TILE_BLACK)

        m = self.memory[by.colour]
        if m:
            if not self.piece or m.hash != self.piece.hash:
                m.delete()

                self.memory[by.colour] = self.piece.copy(MEMORY_COLOUR) if self.piece and self.piece.colour != by.colour else None
                self.place_on_screen(self.memory[by.colour])

        if self.piece:
            self.board.seen[by.colour].add(self.piece)

        return self.piece

    def make_move(self, dx, dy):
        return self.piece, (self.x + dx, self.y + dy)

    def move(self, piece: Piece, is_last=False):
        """
        Try to move to and take on this tile if is_last,
        else try to move through it.

        :rtype: Piece, bool
        :param piece: the moving piece
        :param is_last: is this the last step?
        :return: the piece in this tile, the possibility of this move
        """
        if is_last:
            ret = None

            if self.piece:
                self.board.take(self.piece)
                ret = self.taken.setdefault(self.piece.colour, self.piece)
                self.piece.delete()

            self.set(piece)

            return ret, True
        else:
            if self.piece:
                return self.piece, False

            self.set(piece)

            return None, True

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


class Board(tk.Canvas):
    def __init__(self, master, client, start_file, reinit=False):
        if not reinit:
            tk.Canvas.__init__(self, master=master)
            self.bind("<Expose>", self.draw)
            self.bind("<Button-1>", self._click)
            self.bind("<Configure>", self.resize)
            self.counter = None
        else:
            self.delete('all')

        self.client = client

        self.loaded = False
        self.font = font.Font(family="Cambria", size=-80)

        self.pieces = {Piece.WHITE: [], Piece.BLACK: []}
        self.seen = {Piece.WHITE: set(), Piece.BLACK: set()}
        self.board = np.array([[Tile(x, y, self) for y in range(8)] for x in range(8)])

        self.turn = "wait"
        self.history = []

        self._e1 = None
        self._e2 = None
        self.selection = None

        self.start_file = start_file

    def load(self):
        self.loaded = True
        self.resize()

        constructors = {p.SHAPE: p for p in Piece.pieces}

        with open(self.start_file) as f:
            text = f.read()
        text = "".join(text.split())
        lines = text.split(";")

        for line in lines:
            if not line:
                continue

            colour, data = line.split(":")
            c = Piece.BLACK if colour == "black" else Piece.WHITE

            for pieces in data.split(","):
                shape = pieces[0]
                coords = pieces[1:]

                piece = constructors[shape]

                for x, y in grouper(coords, 2):
                    x = ord(x) - ord('a')
                    y = 8 - int(y)

                    p = piece(self, c)
                    self.board[x, y].load(p)
                    self.pieces.setdefault(p.colour, []).append(p)

    def is_in_bounds(self, x, y):
        return 0 <= x < self.board.shape[0] and 0 <= y < self.board.shape[1]

    def get_tile(self, x, y):
        return self.board[x, y] if self.is_in_bounds(x, y) else None

    def draw(self, event=None):
        if not self.loaded:
            self.load()

        dx = self.winfo_width() / 8
        dy = self.winfo_height() / 8

        for x in range(8):
            for y in range(8):
                self.board[x, y].draw(self, dx, dy)

        for x in range(8):
            for y in range(8):
                piece = self.board[x, y].piece
                if piece is None:
                    continue

        self.redraw()

    def resize(self, event=None):
        dx = self.winfo_width() / 8
        dy = self.winfo_height() / 8

        fontsize = -int(REL_PIECE_SIZE * min(dx, dy))
        self.font.configure(size=fontsize)

        for x in range(8):
            for y in range(8):
                piece = self.board[x, y].piece

                self.board[x, y].place_on_screen(piece)

                for mem_piece in self.board[x, y].memory.values():
                    self.board[x, y].place_on_screen(mem_piece)

        self.redraw()

    def create(self, p, x, y, colour=None):
        colour = p.colour if not colour else colour

        return self.create_text(*self.screen_coord(x, y, True), font=self.font, text=p.APPEARANCE, fill=colour)

    def set_state(self, colour, state):
        for t in self.board.flat:
            t.set_state(colour, state)

    def redraw(self, event=None, colour=None):
        turn = self.turn if not colour else colour

        if turn == "wait":
            self.set_state(Piece.BLACK, "hidden")
            self.set_state(Piece.WHITE, "hidden")
        elif turn == Piece.WHITE:
            self.set_state(Piece.BLACK, "hidden")
            self.set_state(Piece.WHITE, "normal")

            self.vision(Piece.WHITE)
            for p in self.seen[Piece.WHITE]:
                p.set_state("normal")
        elif turn == Piece.BLACK:
            self.set_state(Piece.BLACK, "normal")
            self.set_state(Piece.WHITE, "hidden")

            self.vision(Piece.BLACK)
            for p in self.seen[Piece.BLACK]:
                p.set_state("normal")
        else:
            ...

    def _click(self, event):
        if self._e1:
            self._e2 = event

            x1, y1 = self.grid_coord(self._e1)
            x2, y2 = self.grid_coord(self._e2)
            self.do_move(x1, y1, x2, y2)

            self.delete(self.selection)
            self.selection = None
            self._e1 = None
            self._e2 = None
        else:
            self._e1 = event

            x, y = self.grid_coord(event)
            dx = self.winfo_width() / 8
            dy = self.winfo_height() / 8

            p = self.board[x, y].piece

            if p and p.colour == self.turn:
                self.selection = self.create_text((x + 0.5) * dx, (y + 0.5) * dy, font=self.font, text=p.APPEARANCE, fill="red")
                self.redraw()
                self.tag_raise(self.selection)
            else:
                self._e1 = None

    def grid_coord(self, e):
        return (e.x * 8) // self.winfo_width(), (e.y * 8) // self.winfo_height()

    def screen_coord(self, x, y, c=False):
        if c:
            x += 0.5
            y += 0.5

        return x / 8 * self.winfo_width(), y / 8 * self.winfo_height()

    def vision(self, colour):
        self.seen[colour] = set()

        for t in self.board.flat:
            if t.piece and t.piece.colour == colour:
                t.piece.see(t)

    def play(self, moves, speed=2.0, replay=False):
        if replay:
            self.__init__(self.master, client=self.client, start_file=self.start_file, reinit=True)
            self.load()

            if self.counter:
                self.counter.reset()

            self.turn = Piece.WHITE

            for t in self.board.flat:
                t.toggle_memory()

            self.set_state(Piece.WHITE, "normal")
            self.set_state(Piece.BLACK, "normal")
            self.draw()

        not_turn = Piece.BLACK if self.turn == Piece.WHITE else Piece.WHITE

        for move in moves:
            if not replay:
                self.set_state(self.turn, "normal")
                self.set_state(not_turn, "hidden")

                self.vision(self.turn)
            else:
                self.set_state(Piece.WHITE, "hidden")
                self.set_state(Piece.BLACK, "hidden")
                self.set_state(Piece.WHITE, "normal")
                self.set_state(Piece.BLACK, "normal")
                self.vision(Piece.BLACK)
                self.vision(Piece.WHITE)

            self.update()
            self.update_idletasks()
            time.sleep(speed)

            self.read_move(move)

        if not replay:
            self.set_state(self.turn, "normal")
            self.set_state(not_turn, "hidden")

            self.vision(self.turn)
        else:
            self.set_state(Piece.WHITE, "hidden")
            self.set_state(Piece.BLACK, "hidden")
            self.set_state(Piece.WHITE, "normal")
            self.set_state(Piece.BLACK, "normal")
            self.vision(Piece.BLACK)
            self.vision(Piece.WHITE)

        self.history = moves
        self.win()

    def read_move(self, move):
        x1, y1, x2, y2 = move
        a = ord('a')

        x1, x2 = ord(x1) - a, ord(x2) - a
        y1, y2 = 8 - int(y1), 8 - int(y2)

        self.do_move(x1, y1, x2, y2, send=False)

    def do_move(self, x1, y1, x2, y2, send=True):
        if x1 == x2 and y1 == y2:
            return

        tile = self.board[x1, y1]

        if not tile.piece:
            return

        dx, dy = x2 - x1, y2 - y1
        end = (x2, y2)

        if tile.valid(dx, dy):
            m = (-1, -1)
            for _, m in tile.piece.path(tile, dx, dy):
                ...

            if np.array_equal(m, end):
                tile.piece.transfer(tile, self.board[x2, y2])

                move_str = f"{chr(ord('a') + x1)}{8 - y1}{chr(ord('a') + x2)}{8 - y2}"
                self.history += [move_str]
                if send:
                    self.client.move(move_str)
                    self.turn = "wait"

                self.client.end_turn()

    def win(self):
        white = sum(p.shape == "K" for p in self.pieces[Piece.WHITE])
        black = sum(p.shape == "K" for p in self.pieces[Piece.BLACK])

        won = black == 0 or white == 0
        if white > 0 and black == 0:
            self.create_text(300, 300, font=("Cambria", 20), text="White wins!", fill="#FF0000")
        elif white == 0 and black > 0:
            self.create_text(300, 300, font=("Cambria", 20), text="Black wins!", fill="#FF0000")
        elif white == 0 and black == 0:
            self.create_text(300, 300, font=("Cambria", 20), text="Tie!", fill="#FF0000")

        if won:
            self.turn = "end"

            b = Pawn(self, Piece.BLACK)
            w = Pawn(self, Piece.WHITE)

            for t in self.board.flat:
                t.see(w)
                t.see(b)

            self.set_state(Piece.BLACK, "normal")
            self.set_state(Piece.WHITE, "normal")

            self.client.end_game()

    def take(self, piece):
        if self.counter:
            self.counter.increment(piece)

    def set_counter(self, counter):
        self.counter = counter


class TurnButton(tk.Button):
    def __init__(self, master, board):
        self.text = tk.StringVar()

        tk.Button.__init__(self, master, command=self.start_turn, textvariable=self.text)
        self.board = board
        self.turn = Piece.WHITE

        self.text.set(f"Start {self.turn} turn")

    def start_turn(self):
        if self.board.turn == "wait":
            self.board.turn = self.turn
            self.turn = Piece.BLACK if self.turn == Piece.WHITE else Piece.WHITE
            self.board.redraw()
            self.text.set(f"Start {self.turn} turn")
        elif self.board.turn == "end":
            self.board.play(self.board.history, replay=True)


class KillCounter(tk.Frame):
    class NumStringVar():
        def __init__(self, stringvar):
            self.i = 0
            self.s = stringvar

        def set(self, n):
            self.i = n

        def add(self, n):
            self.i += n
            self.update()

        def update(self):
            self.s.set(str(self.i))

    def __init__(self, master, board, mode="remaining"):
        tk.Frame.__init__(self, master)

        self.board = board
        self.mode = mode
        self.counter = {clr: {piece: KillCounter.NumStringVar(tk.StringVar()) \
                              for piece in Piece.pieces} for clr in COLOURS}

        if self.mode == "remaining":
            ...
        elif self.mode == "taken":
            ...
        else:
            raise ValueError(f"Incorrect mode keyword: {self.mode}")

        piece_num = len(Piece.pieces)

        for i, clr in enumerate(COLOURS):
            clr_label = tk.Label(self, text=clr.title())
            clr_label.grid(row=(piece_num + 2) * i, column=0, columnspan=2)

            for j, piece in enumerate(Piece.pieces):
                piece_label = tk.Label(self, text=piece.APPEARANCE)
                piece_label.grid(row=(piece_num + 2) * i + j + 1, column=0)

                count_label = tk.Label(self, textvariable=self.counter[clr][piece].s)
                count_label.grid(row=(piece_num + 2) * i + j + 1, column=1)

        self.rowconfigure(piece_num + 1, weight=1)

        self.reset()

    def reset(self):
        for clr in COLOURS:
            for piece in Piece.pieces:
                self.counter[clr][piece].set(0)

        if self.mode == "remaining":
            for tile in self.board.board.flat:
                if tile.piece:
                    p = tile.piece
                    self.counter[p.colour][p.__class__].add(1)

        for clr in COLOURS:
            for piece in Piece.pieces:
                self.counter[clr][piece].update()

    def increment(self, piece):
        incr = -1 if self.mode == "remaining" else 1
        clr = piece.colour
        p = piece.__class__

        self.counter[clr][p].add(incr)
        self.counter[clr][p].update()


class Client:
    def __init__(self, client_mode="local", kill_counter=True):
        self.client_mode = client_mode
        self.running = True
        self.waiting = threading.Condition()
        self.colour = None
        self.conn = None

        playfield = tk.Frame(window)
        chessboard = Board(playfield, client=self, start_file='starting_board.txt')
        chessboard.load()

        chessboard.grid(row=0, column=0, sticky='nsew')
        playfield.rowconfigure(0, weight=1)
        playfield.columnconfigure(0, weight=1)

        playfield.grid(row=0, column=0, sticky='nsew')

        if client_mode == "local":
            controlbar = tk.Frame(window)
            turnbutton = TurnButton(controlbar, chessboard)
            turnbutton.grid(row=0, column=0, sticky='nsew')
            controlbar.rowconfigure(0, weight=1)
            controlbar.columnconfigure(0, weight=1)
            controlbar.grid(row=1, column=0, columnspan=2, sticky='nsew')

        if kill_counter:
            displaybar = tk.Frame(window)
            killcounter = KillCounter(displaybar, chessboard)
            killcounter.grid(row=0, column=0, sticky='nsew')
            displaybar.rowconfigure(0, weight=1)
            displaybar.columnconfigure(0, weight=1)
            displaybar.grid(row=0, column=1, sticky='nsew')

            chessboard.set_counter(killcounter)

        window.columnconfigure(0, weight=8)
        window.columnconfigure(1, weight=1)
        window.rowconfigure(0, weight=8)
        window.rowconfigure(1, weight=1)



        window.columnconfigure(0, weight=1)
        window.rowconfigure(0, weight=8)
        window.rowconfigure(1, weight=1)

        self.board = chessboard

        if client_mode == "online":
            server = input("Server ip: ")
            port = input("Port: ")
            room = input("Room (enter 'direct' to connect without intermediate server): ")

            port = int(port)

            def connect():
                self.conn = transit("direct" if room == "direct" else "proxy", server, port, room=room)
                self.negotiate_colour()
            window.after(1000, connect)

        if client_mode != "replay":
            window.mainloop()

    def replay(self, moves):
        window.after(500, lambda: self.board.play(moves, replay=True))
        window.mainloop()

    def negotiate_colour(self):
        roll = int(np.random.rand() * 1e6)

        self.conn.send(str(roll).encode())
        other_roll = int(self.conn.recv(1024).decode())

        self.conn_thread = threading.Thread(target=self.conn_func)
        self.conn_thread.start()

        if roll > other_roll:
            self.colour = Piece.WHITE
            self.board.turn = self.colour
        else:
            self.colour = Piece.BLACK
            self.board.turn = self.colour
            self.board.turn = "wait"

            with self.waiting:
                self.waiting.notify()

        self.redraw()

    def redraw(self):
        self.board.redraw(colour=self.colour)

    def end_turn(self):
        self.board.win()

        if not self.running:
            return

        if self.client_mode == "local":
            self.board.redraw()
        else:
            self.redraw()
            with self.waiting:
                self.waiting.notify()

    def end_game(self):
        self.running = False

        print(self.board.history)

        if self.client_mode == "online":
            self.conn.close()

            with self.waiting:
                self.waiting.notify()

    def move(self, move_str):
        if self.client_mode == "online":
            self.conn.send(move_str.encode())

    def conn_func(self):
        with self.waiting:
            self.waiting.wait()
            while self.running:
                msg = self.conn.recv(1024)
                self.board.set_state(Piece.BLACK, "hidden")
                self.board.set_state(Piece.WHITE, "hidden")
                self.board.read_move(msg.decode())
                self.redraw()
                self.board.turn = self.colour

                if self.running:
                    self.waiting.wait()


c = Client(client_mode="online")
#c.replay(['e3e4', 'e5e4', 'd4e4', 'd5e4'])
