# -*- coding: utf-8 -*-
"""
Script de UMA VEZ SÓ (não roda no sistema em produção) — converte os
arquivos JSON brutos da Bíblia Livre (BLIVRE, domínio público,
https://github.com/damarals/biblias) pro formato compacto usado pelo
buscador de versículo por texto (busca_versiculo_texto.py).

Gera biblia_texto_dominio_publico.json na raiz do projeto.
"""

import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from biblia_livros import LIVROS

PASTA_BRUTA = "BLIVRE_raw"
ARQUIVO_SAIDA = "biblia_texto_dominio_publico.json"

# Mapa código USX/OSIS (usado pelos arquivos da BLIVRE) -> nome canônico
# usado neste projeto (mesma ordem/nomenclatura de biblia_livros.py).
CODIGO_PARA_CANONICO = {
    "GEN": "Gênesis", "EXO": "Êxodo", "LEV": "Levítico", "NUM": "Números",
    "DEU": "Deuteronômio", "JOS": "Josué", "JDG": "Juízes", "RUT": "Rute",
    "1SA": "1 Samuel", "2SA": "2 Samuel", "1KI": "1 Reis", "2KI": "2 Reis",
    "1CH": "1 Crônicas", "2CH": "2 Crônicas", "EZR": "Esdras", "NEH": "Neemias",
    "EST": "Ester", "JOB": "Jó", "PSA": "Salmos", "PRO": "Provérbios",
    "ECC": "Eclesiastes", "SNG": "Cânticos", "ISA": "Isaías", "JER": "Jeremias",
    "LAM": "Lamentações", "EZK": "Ezequiel", "DAN": "Daniel", "HOS": "Oséias",
    "JOL": "Joel", "AMO": "Amós", "OBA": "Obadias", "JON": "Jonas",
    "MIC": "Miquéias", "NAM": "Naum", "HAB": "Habacuque", "ZEP": "Sofonias",
    "HAG": "Ageu", "ZEC": "Zacarias", "MAL": "Malaquias",
    "MAT": "Mateus", "MRK": "Marcos", "LUK": "Lucas", "JHN": "João",
    "ACT": "Atos", "ROM": "Romanos", "1CO": "1 Coríntios", "2CO": "2 Coríntios",
    "GAL": "Gálatas", "EPH": "Efésios", "PHP": "Filipenses", "COL": "Colossenses",
    "1TH": "1 Tessalonicenses", "2TH": "2 Tessalonicenses",
    "1TI": "1 Timóteo", "2TI": "2 Timóteo", "TIT": "Tito", "PHM": "Filemom",
    "HEB": "Hebreus", "JAS": "Tiago", "1PE": "1 Pedro", "2PE": "2 Pedro",
    "1JN": "1 João", "2JN": "2 João", "3JN": "3 João", "JUD": "Judas",
    "REV": "Apocalipse",
}


def _remover_acentos(s):
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto):
    """Mesma normalização usada em parser_referencias.py, pra garantir
    que o texto falado (já normalizado) e o texto bíblico (normalizado
    aqui) fiquem no mesmo 'alfabeto' na hora de comparar."""
    texto = texto.lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[.,;:!?()\[\]\"'\u201c\u201d\u2018\u2019]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


def main():
    assert len(CODIGO_PARA_CANONICO) == 66, \
        f"esperava 66 livros mapeados, achei {len(CODIGO_PARA_CANONICO)}"
    assert set(CODIGO_PARA_CANONICO.values()) == set(LIVROS.keys()), \
        "nomes canônicos não batem com biblia_livros.py"

    corpus = {}  # "Livro|capitulo|versiculo" -> texto normalizado
    total_versiculos = 0

    for codigo, nome_canonico in CODIGO_PARA_CANONICO.items():
        caminho = os.path.join(PASTA_BRUTA, f"{codigo}.json")
        with open(caminho, "r", encoding="utf-8") as f:
            dados_livro = json.load(f)

        for capitulo in dados_livro["chapters"]:
            num_cap = capitulo["number"]
            for versiculo in capitulo["verses"]:
                num_vers = versiculo["number"]
                texto_norm = normalizar_texto(versiculo["text"])
                chave = f"{nome_canonico}|{num_cap}|{num_vers}"
                corpus[chave] = texto_norm
                total_versiculos += 1

    with open(ARQUIVO_SAIDA, "w", encoding="utf-8") as f:
        json.dump(corpus, f, ensure_ascii=False, separators=(",", ":"))

    tamanho_kb = os.path.getsize(ARQUIVO_SAIDA) / 1024
    print(f"OK: {total_versiculos} versículos convertidos.")
    print(f"Arquivo gerado: {ARQUIVO_SAIDA} ({tamanho_kb:.0f} KB)")


if __name__ == "__main__":
    main()
