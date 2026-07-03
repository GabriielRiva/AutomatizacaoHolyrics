# -*- coding: utf-8 -*-
"""
Dicionário dos 66 livros da Bíblia com variações faladas em português
(nome completo, abreviações comuns, formas com "primeiro/segundo/terceiro",
formas com "1/2/3", "I/II/III" etc.)

Cada entrada: chave = nome canônico (usado para montar a referência final
que vai pro Holyrics), valor = lista de aliases (todos em minúsculas, sem
acento — a normalização de acento é feita no parser).

IMPORTANTE: aliases multi-palavra são tratados como frases inteiras no
parser (regex com \b), então a ordem de compostos vs. simples não importa
aqui, mas colocar as formas mais específicas primeiro ajuda na legibilidade.

single_chapter=True marca os livros de capítulo único (Obadias, Filemom,
2 João, 3 João, Judas) — nesses casos "livro 6" significa versículo 6,
não capítulo 6.
"""

LIVROS = {
    # ---------------- ANTIGO TESTAMENTO ----------------
    "Gênesis": {
        "aliases": ["genesis", "gen"],
    },
    "Êxodo": {
        "aliases": ["exodo", "ex"],
    },
    "Levítico": {
        "aliases": ["levitico", "lev"],
    },
    "Números": {
        "aliases": ["numeros", "nm"],
    },
    "Deuteronômio": {
        "aliases": ["deuteronomio", "dt"],
    },
    "Josué": {
        "aliases": ["josue", "js"],
    },
    "Juízes": {
        "aliases": ["juizes", "jz"],
    },
    "Rute": {
        "aliases": ["rute", "rt"],
    },
    "1 Samuel": {
        "aliases": [
            "primeiro samuel", "primeira de samuel", "primeiro de samuel",
            "um samuel", "1 samuel", "i samuel",
        ],
    },
    "2 Samuel": {
        "aliases": [
            "segundo samuel", "segunda de samuel", "segundo de samuel",
            "dois samuel", "2 samuel", "ii samuel",
        ],
    },
    "1 Reis": {
        "aliases": [
            "primeiro reis", "primeira de reis", "primeiro de reis",
            "um reis", "1 reis", "i reis",
        ],
    },
    "2 Reis": {
        "aliases": [
            "segundo reis", "segunda de reis", "segundo de reis",
            "dois reis", "2 reis", "ii reis",
        ],
    },
    "1 Crônicas": {
        "aliases": [
            "primeiro cronicas", "primeira de cronicas", "primeiro de cronicas",
            "um cronicas", "1 cronicas", "i cronicas",
        ],
    },
    "2 Crônicas": {
        "aliases": [
            "segundo cronicas", "segunda de cronicas", "segundo de cronicas",
            "dois cronicas", "2 cronicas", "ii cronicas",
        ],
    },
    "Esdras": {
        "aliases": ["esdras", "ed"],
    },
    "Neemias": {
        "aliases": ["neemias", "ne"],
    },
    "Ester": {
        "aliases": ["ester", "et"],
    },
    "Jó": {
        "aliases": ["jo", "job"],  # cuidado: "jo" colide com Jô; desambiguar no parser por contexto
    },
    "Salmos": {
        "aliases": ["salmos", "salmo", "sl"],
    },
    "Provérbios": {
        "aliases": ["proverbios", "proverbio", "pv"],
    },
    "Eclesiastes": {
        "aliases": ["eclesiastes", "ec", "coelete"],
    },
    "Cânticos": {
        "aliases": [
            "canticos", "cantico dos canticos", "canticos de salomao", "ct",
        ],
    },
    "Isaías": {
        "aliases": ["isaias", "is"],
    },
    "Jeremias": {
        "aliases": ["jeremias", "jr"],
    },
    "Lamentações": {
        "aliases": ["lamentacoes", "lm"],
    },
    "Ezequiel": {
        "aliases": ["ezequiel", "ez"],
    },
    "Daniel": {
        "aliases": ["daniel", "dn"],
    },
    "Oséias": {
        "aliases": ["oseias", "os"],
    },
    "Joel": {
        "aliases": ["joel", "jl"],
    },
    "Amós": {
        "aliases": ["amos", "am"],
    },
    "Obadias": {
        "aliases": ["obadias", "ob"],
        "single_chapter": True,
    },
    "Jonas": {
        "aliases": ["jonas", "jn"],
    },
    "Miquéias": {
        "aliases": ["miqueias", "mq"],
    },
    "Naum": {
        "aliases": ["naum", "na"],
    },
    "Habacuque": {
        "aliases": ["habacuque", "hc"],
    },
    "Sofonias": {
        "aliases": ["sofonias", "sf"],
    },
    "Ageu": {
        "aliases": ["ageu", "ag"],
    },
    "Zacarias": {
        "aliases": ["zacarias", "zc"],
    },
    "Malaquias": {
        "aliases": ["malaquias", "ml"],
    },

    # ---------------- NOVO TESTAMENTO ----------------
    "Mateus": {
        "aliases": ["mateus", "mt"],
    },
    "Marcos": {
        "aliases": ["marcos", "mc"],
    },
    "Lucas": {
        "aliases": ["lucas", "lc"],
    },
    "João": {
        # obs: "jo" NÃO entra aqui de propósito — é abreviação escrita,
        # e falado "João" normaliza pra "joao", nunca pra "jo". O alias
        # "jo" fica reservado só pro livro Jó (falado "Jó" -> "jo" sem
        # acento). Ver LIVROS["Jó"].
        "aliases": ["joao"],
    },
    "Atos": {
        "aliases": ["atos", "atos dos apostolos", "at"],
    },
    "Romanos": {
        "aliases": ["romanos", "rm"],
    },
    "1 Coríntios": {
        "aliases": [
            "primeiro corintios", "primeira de corintios", "primeiro de corintios",
            "um corintios", "1 corintios", "i corintios",
        ],
    },
    "2 Coríntios": {
        "aliases": [
            "segundo corintios", "segunda de corintios", "segundo de corintios",
            "dois corintios", "2 corintios", "ii corintios",
        ],
    },
    "Gálatas": {
        "aliases": ["galatas", "gl"],
    },
    "Efésios": {
        "aliases": ["efesios", "ef"],
    },
    "Filipenses": {
        "aliases": ["filipenses", "fp"],
    },
    "Colossenses": {
        "aliases": ["colossenses", "cl"],
    },
    "1 Tessalonicenses": {
        "aliases": [
            "primeiro tessalonicenses", "primeira de tessalonicenses",
            "primeiro de tessalonicenses", "um tessalonicenses",
            "1 tessalonicenses", "i tessalonicenses",
        ],
    },
    "2 Tessalonicenses": {
        "aliases": [
            "segundo tessalonicenses", "segunda de tessalonicenses",
            "segundo de tessalonicenses", "dois tessalonicenses",
            "2 tessalonicenses", "ii tessalonicenses",
        ],
    },
    "1 Timóteo": {
        "aliases": [
            "primeiro timoteo", "primeira de timoteo", "primeiro de timoteo",
            "um timoteo", "1 timoteo", "i timoteo",
        ],
    },
    "2 Timóteo": {
        "aliases": [
            "segundo timoteo", "segunda de timoteo", "segundo de timoteo",
            "dois timoteo", "2 timoteo", "ii timoteo",
        ],
    },
    "Tito": {
        "aliases": ["tito", "tt"],
    },
    "Filemom": {
        "aliases": ["filemom", "fm"],
        "single_chapter": True,
    },
    "Hebreus": {
        "aliases": ["hebreus", "hb"],
    },
    "Tiago": {
        "aliases": ["tiago", "tg"],
    },
    "1 Pedro": {
        "aliases": [
            "primeiro pedro", "primeira de pedro", "primeiro de pedro",
            "um pedro", "1 pedro", "i pedro",
        ],
    },
    "2 Pedro": {
        "aliases": [
            "segundo pedro", "segunda de pedro", "segundo de pedro",
            "dois pedro", "2 pedro", "ii pedro",
        ],
    },
    "1 João": {
        "aliases": [
            "primeiro joao", "primeira de joao", "primeiro de joao",
            "um joao", "1 joao", "i joao",
        ],
    },
    "2 João": {
        "aliases": [
            "segundo joao", "segunda de joao", "segundo de joao",
            "dois joao", "2 joao", "ii joao",
        ],
        "single_chapter": True,
    },
    "3 João": {
        "aliases": [
            "terceiro joao", "terceira de joao", "terceiro de joao",
            "tres joao", "3 joao", "iii joao",
        ],
        "single_chapter": True,
    },
    "Judas": {
        "aliases": ["judas", "jd"],
        "single_chapter": True,
    },
    "Apocalipse": {
        "aliases": ["apocalipse", "ap"],
    },
}

SINGLE_CHAPTER_BOOKS = {
    nome for nome, dados in LIVROS.items() if dados.get("single_chapter")
}

# Numeração canônica dos livros (1-66), na ordem padrão usada por sistemas
# de referência bíblica — inclusive o formato de ID do Holyrics
# (BBCCCVVV: 2 dígitos de livro + 3 de capítulo + 3 de versículo).
# A ordem de inserção do dicionário LIVROS já segue essa numeração padrão,
# então só precisamos enumerar.
NUMERO_LIVRO = {nome: i + 1 for i, nome in enumerate(LIVROS.keys())}

# Gera automaticamente variantes sem a preposição "de" para os livros
# numerados, já que na fala é comum tanto "primeira de coríntios" quanto
# "primeira coríntios" / "primeiro coríntios".
for _nome, _dados in LIVROS.items():
    _extras = []
    for _alias in _dados["aliases"]:
        if " de " in _alias:
            _extras.append(_alias.replace(" de ", " "))
            # variante com "livro" no meio: "segundo de corintios" ->
            # "segundo livro de corintios" (fala tipo "o segundo livro de
            # Coríntios")
            _extras.append(_alias.replace(" de ", " livro de "))
    for _extra in _extras:
        if _extra not in _dados["aliases"]:
            _dados["aliases"].append(_extra)
