"""Split PGN collections and turn movetext into SAN tokens."""

from __future__ import annotations

import re


RESULTS = {"1-0", "0-1", "1/2-1/2", "*"}


def split_games(text):
    chunks = re.split(r"\n(?=\[Event )", text)
    games = []
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk.startswith("[Event "):
            games.append(chunk)
    return games


def game_headers(game):
    return dict(re.findall(r'\[(\w+)\s+"([^"]*)"\]', game))


def game_movetext(game):
    idx = game.rfind("]")
    return game[idx + 1:] if idx != -1 else game


def strip_comments_and_variations(movetext):
    out = []
    brace = 0
    paren = 0
    for char in movetext:
        if char == "{":
            brace += 1
        elif char == "}" and brace:
            brace -= 1
        elif brace:
            continue
        elif char == "(":
            paren += 1
        elif char == ")" and paren:
            paren -= 1
        elif paren:
            continue
        else:
            out.append(char)
    return re.sub(r"\$\d+", " ", "".join(out))


def movetext_tokens(movetext):
    tokens = []
    for raw in strip_comments_and_variations(movetext).split():
        if raw in RESULTS:
            break
        token = re.sub(r"^\d+\.+", "", raw)
        token = token.replace("!", "").replace("?", "")
        if token:
            tokens.append(token)
    return tokens


def describe_game(headers):
    return "%s vs %s, %s round %s" % (
        headers.get("White", "?"),
        headers.get("Black", "?"),
        headers.get("Event", "?"),
        headers.get("Round", "?"),
    )
