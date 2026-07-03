# -*- coding: utf-8 -*-
"""
Conversor de números falados em português (por extenso) para inteiros.
Cobre 0-999, suficiente para capítulos (máx. 176, Salmo 119) e versículos
(máx. 176 também).

Uso principal: dado um texto já normalizado (minúsculo, sem acento),
localizar sequências de "palavras-número" consecutivas e substituí-las
por um único token numérico (dígitos), preservando o resto da frase.
"""

import re

UNIDADES = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3,
    "quatro": 4, "cinco": 5, "seis": 6, "sete": 7, "oito": 8, "nove": 9,
}

DEZ_A_DEZENOVE = {
    "dez": 10, "onze": 11, "doze": 12, "treze": 13, "catorze": 14,
    "quatorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17,
    "dezoito": 18, "dezenove": 19,
}

DEZENAS = {
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50,
    "sessenta": 60, "setenta": 70, "oitenta": 80, "noventa": 90,
}

CENTENAS = {
    "cem": 100, "cento": 100, "duzentos": 200, "trezentos": 300,
    "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
    "setecentos": 700, "oitocentos": 800, "novecentos": 900,
}

PALAVRAS_NUMERO = (
    set(UNIDADES) | set(DEZ_A_DEZENOVE) | set(DEZENAS) | set(CENTENAS) | {"e"}
)

# "e" só conta como parte de número se estiver entre duas palavras-número
# (ex: "cento e vinte"), então tratamos isso na hora de escanear o texto.


def _valor_palavra(p):
    if p in UNIDADES:
        return UNIDADES[p]
    if p in DEZ_A_DEZENOVE:
        return DEZ_A_DEZENOVE[p]
    if p in DEZENAS:
        return DEZENAS[p]
    if p in CENTENAS:
        return CENTENAS[p]
    return None


def extrair_grupos_numericos(tokens):
    """
    Recebe lista de tokens (palavras) já normalizados (sem acento, minúsculo).
    Retorna lista de (indice_inicio, indice_fim_exclusivo, valor_inteiro)
    para cada sequência contígua de palavras-número encontrada no texto.
    Regras de composição pt-BR: centena + [dezena|dezenove] + [e + unidade]
    Ex: "cento e setenta e seis" -> 176
        "trinta e dois" -> 32
        "treze" -> 13
        "vinte" -> 20
    """
    def _peek_sem_e(pos):
        """Retorna a posição seguinte pulando um 'e' de ligação, se houver
        um 'e' e o token depois dele for uma palavra-número."""
        if pos < n and tokens[pos] == "e" and pos + 1 < n \
                and _valor_palavra(tokens[pos + 1]) is not None:
            return pos + 1
        return pos

    grupos = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        if _valor_palavra(tok) is None:
            i += 1
            continue

        inicio = i
        total = 0
        consumiu_algo = False

        # 1) centena (cem/cento/duzentos/...)
        if tok in CENTENAS:
            total += CENTENAS[tok]
            i += 1
            consumiu_algo = True
            i = _peek_sem_e(i)

        # 2) dezena (vinte..noventa) OU dez-a-dezenove OU unidade isolada
        if i < n and tokens[i] in DEZENAS:
            total += DEZENAS[tokens[i]]
            i += 1
            consumiu_algo = True
            j = _peek_sem_e(i)
            # dezena + unidade (ex: "vinte e dois", "trinta e um")
            if j < n and tokens[j] in UNIDADES:
                total += UNIDADES[tokens[j]]
                i = j + 1
        elif i < n and tokens[i] in DEZ_A_DEZENOVE:
            total += DEZ_A_DEZENOVE[tokens[i]]
            i += 1
            consumiu_algo = True
        elif i < n and tokens[i] in UNIDADES:
            total += UNIDADES[tokens[i]]
            i += 1
            consumiu_algo = True

        if not consumiu_algo:
            i = inicio + 1
            continue

        grupos.append((inicio, i, total))

    return grupos


def substituir_numeros_por_digitos(texto_normalizado):
    """
    Recebe texto já normalizado (ver parser_referencias.normalizar) e
    devolve o mesmo texto com sequências de números por extenso trocadas
    por dígitos. Números que já vierem em dígitos (ex: "1 corintios")
    são preservados como estão.
    """
    tokens = texto_normalizado.split()
    grupos = extrair_grupos_numericos(tokens)

    if not grupos:
        return texto_normalizado

    resultado = []
    cursor = 0
    for inicio, fim, valor in grupos:
        resultado.extend(tokens[cursor:inicio])
        resultado.append(str(valor))
        cursor = fim
    resultado.extend(tokens[cursor:])
    return " ".join(resultado)
