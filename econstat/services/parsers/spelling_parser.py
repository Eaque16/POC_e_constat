"""Décodage prudent de l'épellation française produite par Whisper."""

import re
import unicodedata

LETTER_WORDS = {
    "a": "A",
    "be": "B",
    "b": "B",
    "ce": "C",
    "c": "C",
    "de": "D",
    "d": "D",
    "e": "E",
    "effe": "F",
    "ef": "F",
    "f": "F",
    "ge": "G",
    "g": "G",
    "ache": "H",
    "h": "H",
    "i": "I",
    "ji": "J",
    "j": "J",
    "ka": "K",
    "k": "K",
    "elle": "L",
    "l": "L",
    "eme": "M",
    "m": "M",
    "enne": "N",
    "n": "N",
    "o": "O",
    "pe": "P",
    "p": "P",
    "ku": "Q",
    "q": "Q",
    "ere": "R",
    "r": "R",
    "esse": "S",
    "s": "S",
    "te": "T",
    "t": "T",
    "u": "U",
    "ve": "V",
    "v": "V",
    "double ve": "W",
    "double v": "W",
    "ix": "X",
    "x": "X",
    "i grec": "Y",
    "y": "Y",
    "zede": "Z",
    "z": "Z",
    "apostrophe": "'",
    "tiret": "-",
}


def _plain(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def parse_spelling(value: str) -> str | None:
    plain = _plain(value).replace(",", " ").replace(".", " ")
    tokens = re.findall(r"[a-z]+|['-]", plain)
    output: list[str] = []
    index = 0
    while index < len(tokens):
        pair = " ".join(tokens[index : index + 2])
        if pair in LETTER_WORDS:
            output.append(LETTER_WORDS[pair])
            index += 2
            continue
        token = tokens[index]
        if (
            token in {"n", "d", "l"}
            and index + 1 < len(tokens)
            and tokens[index + 1] == "apostrophe"
        ):
            output.extend((token.upper(), "'"))
            index += 2
            continue
        letter = LETTER_WORDS.get(token)
        if letter is None:
            return None
        output.append(letter)
        index += 1
    result = "".join(output).strip("'-")
    return result if len(result.replace("'", "").replace("-", "")) >= 2 else None
