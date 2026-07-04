# -*- coding: utf-8 -*-
"""
Reconhece qual versículo bíblico está sendo CITADO DE COR (recitado de
memória, sem falar a referência "livro capítulo versículo"), comparando
o texto transcrito da fala contra um corpus com o texto de toda a
Bíblia.

Corpus usado: Bíblia Livre (BLIVRE, 2018), que é de DOMÍNIO PÚBLICO
(https://github.com/damarals/biblias, licença "public-domain" no
próprio metadata). Usamos esse texto só para efeito de COMPARAÇÃO —
o versículo de fato exibido no telão continua vindo da versão que a
igreja já tem instalada e configurada no Holyrics (NVI, ACF, etc.),
via holyrics_client.py. O corpus aqui é só uma "impressão digital" do
texto bíblico pra saber QUAL é o versículo, não pra mostrar esse texto
específico pra ninguém.

IMPORTANTE — limitações esperadas:
  - A fala nunca bate 100% com o texto escrito (STT erra, o pregador
    parafraseia, muda uma palavra aqui e ali). Por isso o limiar de
    confiança aqui é mais exigente que o do parser de referência
    direta (parser_referencias.py) — prefere não sugerir nada a
    sugerir um versículo errado.
  - Frases curtas ou genéricas (poucas palavras "raras") são
    descartadas de propósito, porque combinam com versículos demais
    pra dar uma resposta confiável.
"""

import difflib
import json
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from typing import Optional

# Palavras comuns demais no português bíblico pra servirem de "isca" na
# busca por candidatos — apareceriam em milhares de versículos e só
# tornariam a busca mais lenta sem ajudar a distinguir nada. Ainda
# entram no cálculo de similaridade final, só não são usadas como
# ponto de partida pra encontrar candidatos.
PALAVRAS_COMUNS = {
    "que", "para", "com", "uma", "não", "nao", "seu", "sua", "seus", "suas",
    "dos", "das", "por", "mas", "como", "quando", "aquele", "aquela",
    "ele", "ela", "eles", "elas", "isso", "isto", "essa", "esse", "essas",
    "esses", "esta", "este", "estas", "estes", "todo", "toda", "todos",
    "todas", "sobre", "entre", "assim", "disse", "dizendo", "falou",
    "então", "entao", "havia", "porque", "onde", "qual", "quais",
}

LIMIAR_CONFIANCA_PADRAO = 0.6
MARGEM_MINIMA_PADRAO = 0.10
MIN_PALAVRAS_SIGNIFICATIVAS = 3
MAX_CANDIDATOS_AVALIADOS = 20


@dataclass
class VersiculoReconhecidoPorTexto:
    livro: str
    capitulo: int
    versiculo: int
    confianca: float
    texto_corpus: str
    texto_original: str

    def referencia_formatada(self) -> str:
        return f"{self.livro} {self.capitulo}:{self.versiculo}"


def _remover_acentos(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar_texto(texto: str) -> str:
    """Mesma normalização usada em parser_referencias.py — garante que
    fala transcrita e corpus bíblico fiquem no mesmo 'alfabeto'."""
    texto = texto.lower()
    texto = _remover_acentos(texto)
    texto = re.sub(r"[.,;:!?()\[\]\"'\u201c\u201d\u2018\u2019]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


class CorpusBiblico:
    """
    Carrega o corpus de texto bíblico (gerado por
    converter_biblia_dominio_publico.py) e monta um índice invertido
    pra achar candidatos rapidamente, sem comparar contra os 31 mil
    versículos um por um a cada frase reconhecida.
    """

    def __init__(self, caminho_json):
        with open(caminho_json, "r", encoding="utf-8") as f:
            bruto = json.load(f)

        # chave "Livro|capitulo|versiculo" -> lista de palavras do versículo
        self.versiculos = {chave: texto.split() for chave, texto in bruto.items()}

        # índice invertido: palavra "rara" -> conjunto de chaves de
        # versículos que a contêm
        self.indice = {}
        for chave, palavras in self.versiculos.items():
            vistas_neste_versiculo = set()
            for palavra in palavras:
                if len(palavra) < 4 or palavra in PALAVRAS_COMUNS:
                    continue
                if palavra in vistas_neste_versiculo:
                    continue
                vistas_neste_versiculo.add(palavra)
                self.indice.setdefault(palavra, set()).add(chave)

    def buscar(self, texto_falado_normalizado, limiar_confianca=LIMIAR_CONFIANCA_PADRAO,
               margem_minima=MARGEM_MINIMA_PADRAO,
               min_palavras_significativas=MIN_PALAVRAS_SIGNIFICATIVAS):
        """
        Retorna VersiculoReconhecidoPorTexto se achar um candidato claro
        o bastante, ou None se não achar nada com confiança suficiente
        (inclusive quando o texto for curto/genérico demais pra buscar
        com segurança).
        """
        tokens = texto_falado_normalizado.split()

        palavras_isca = [
            t for t in tokens if len(t) >= 4 and t not in PALAVRAS_COMUNS
        ]
        if len(palavras_isca) < min_palavras_significativas:
            return None

        contagem = Counter()
        for palavra in palavras_isca:
            for chave in self.indice.get(palavra, ()):
                contagem[chave] += 1

        if not contagem:
            return None

        candidatos = [chave for chave, _ in contagem.most_common(MAX_CANDIDATOS_AVALIADOS)]

        pontuados = []
        for chave in candidatos:
            palavras_versiculo = self.versiculos[chave]
            razao = difflib.SequenceMatcher(None, tokens, palavras_versiculo).ratio()
            pontuados.append((razao, chave))

        pontuados.sort(reverse=True)
        melhor_pontuacao, melhor_chave = pontuados[0]
        segunda_pontuacao = pontuados[1][0] if len(pontuados) > 1 else 0.0

        if melhor_pontuacao < limiar_confianca:
            return None
        if (melhor_pontuacao - segunda_pontuacao) < margem_minima and len(pontuados) > 1:
            # ambíguo demais entre dois versículos parecidos — melhor
            # não arriscar sugerir o errado
            return None

        livro, capitulo_str, versiculo_str = melhor_chave.split("|")
        return VersiculoReconhecidoPorTexto(
            livro=livro,
            capitulo=int(capitulo_str),
            versiculo=int(versiculo_str),
            confianca=melhor_pontuacao,
            texto_corpus=" ".join(self.versiculos[melhor_chave]),
            texto_original=texto_falado_normalizado,
        )


def carregar_corpus(caminho_json):
    """Ponto de entrada usado por sistema_completo.py. Isolado numa
    função à parte pra poder ser chamado numa thread de carregamento
    em segundo plano, junto com o modelo Vosk."""
    return CorpusBiblico(caminho_json)


if __name__ == "__main__":
    import sys

    caminho = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "biblia_texto_dominio_publico.json")
    print(f"Carregando corpus de {caminho}...")
    corpus = carregar_corpus(caminho)
    print(f"OK: {len(corpus.versiculos)} versículos, "
          f"{len(corpus.indice)} palavras no índice.\n")

    testes = [
        "porque deus amou o mundo de tal maneira que deu o seu filho unigenito",
        "o senhor e o meu pastor nada me faltara",
        "tudo posso naquele que me fortalece",
        "tenho boas novas de grande alegria",
        "tudo bem hoje o culto vai comecar daqui a pouco",
        "tudo posso",
    ]
    for t in testes:
        t_norm = normalizar_texto(t)
        resultado = corpus.buscar(t_norm)
        if resultado:
            print(f"{t!r}\n  -> {resultado.referencia_formatada()} "
                  f"(confiança={resultado.confianca:.2f})\n")
        else:
            print(f"{t!r}\n  -> nenhum versículo reconhecido com confiança suficiente\n")
