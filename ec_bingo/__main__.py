# SPDX-License-Identifier: BlueOak-1.0.0

import asyncio
import base64
import functools
import io
import itertools
import json
import random
import operator
import os
import sys
import textwrap
from pathlib import Path

import aiohttp
import aioec
from wand.image import Image
from wand.drawing import Drawing

from .board import Bingo
from .utils import scale_resolution

_coords = list(itertools.product((284, 548, 813, 1078, 1342), (327, 592, 857, 1121, 1387)))
COORDS = dict(zip('BINGO', (_coords[i:i+Bingo.HEIGHT] for i in range(0, len(_coords), Bingo.HEIGHT))))
del COORDS['N'][2]  # free space
del _coords

# width and height (within the border) of one square
SQUARE_SIZE = 256

HERE = Path(__file__).parent

def download(emote_name):
    async def read(name):
        async with \
            aiohttp.ClientSession() as sess, \
            aioec.Client() as client, \
            sess.get((await client.emote(emote_name)).url) as resp \
        :
            return await resp.read()
    try:
        return asyncio.get_event_loop().run_until_complete(read(emote_name))
    except aioec.NotFound:
        print(f'Emote "{emote_name}" not found.', file=sys.stderr)
        sys.exit(2)

def draw_board(cats):
    img = Image(filename=HERE / "bingo_board_base.png")
    with Drawing() as draw:
        draw.font = str(HERE / 'DejaVuSans.ttf')
        draw.font_size = 40
        for c, (x, y) in zip(cats, functools.reduce(operator.concat, COORDS.values())):
            draw.text(x, y, "\n".join(textwrap.wrap(c, 10)))
        draw(img)
    return img

def render(board_data):
    img = draw_board(board_data['categories'])
    marks = board_data['emotes'].items()
    with Drawing() as draw:
        mark(draw, img, ((point, base64.b64decode(img.encode('ascii'))) for point, img in marks))
        draw(img)
    return img

def parse_point(point):
    col, row = point
    return col, int(row)

def mark(draw, img, marks):
    for point, eimg in marks:
        col, row = parse_point(point)
        left, top = COORDS[col][row - 1]

        half = SQUARE_SIZE // 2
        with Image(blob=eimg) as eimg:
            eimg.resize(*scale_resolution((img.width, img.height), (half, half)))
            draw.composite(
                operator='over',
                left=left+half-65, top=top+25,
                width=eimg.width, height=eimg.height,
                image=eimg)

def new():
    with open(HERE / "bingo_categories.txt") as f:
        cats = list(map(str.rstrip, f))
    random.shuffle(cats)

    board = Bingo()
    board.data = {'categories': cats[:-26:-1], 'emotes': {}}
    return vars(board)

if __name__ == "__main__":
    import sys

    if len(sys.argv) == 1:
        print("""\
Usage:
	python -m ec_bingo new > board.json
	python -m ec_bingo mark <point> <name> < board.json > new-board.json
	python -m ec_bingo unmark <point> < board.json > new-board.json
	python -m ec_bingo render < board.json > board.png

Creates a new bingo board for use with Emote Collector,
or modifies a point on an existing board.

Mark and unmark read board data as JSON from stdin and writes board data to stdout.
New takes no arguments and no input, and writes board data to stdout.
Render reads board data from stdin and writes a PNG image to stdout.
""", file=sys.stderr)
        sys.exit(0)

    if sys.argv[1] == 'new':
        json.dump(new(), sys.stdout)
        print()
        sys.exit(0)
    if sys.argv[1] not in ('render', 'mark', 'unmark'):
        print("Unrecognized argument(s):", *sys.argv, file=sys.stderr)
        sys.exit(1)

    board_data = json.load(sys.stdin)

    if sys.argv[1] == 'render':
        with render(board_data['data']) as img, img.convert('png') as converted:
            converted.save(file=sys.stdout.buffer)
        sys.exit(0)

    try:
        _, _, point, *rest = sys.argv
    except ValueError:
        print("Not enough arguments supplied.", file=sys.stderr)
        sys.exit(1)
    if point == 'N3':
        print('Point may not be "N3".', file=sys.stderr)
        sys.exit(1)

    board = Bingo()
    vars(board).update(board_data)

    col, row = parse_point(point)
    if sys.argv[1] == 'unmark':
        board[col, row] = 0
        del board.data['emotes'][point]
    else:  # mark
        try:
            emote, = rest
        except ValueError:
            print("Not enough arguments supplied.", file=sys.stderr)
            sys.exit(1)
        board[col, row] = 1
        board.data['emotes'][point] = base64.b64encode(download(emote)).decode('ascii')

    json.dump(vars(board), sys.stdout)
    print()
    sys.exit(0)
