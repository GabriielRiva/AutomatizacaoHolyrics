# -*- coding: utf-8 -*-
"""
Parser de referências bíblicas faladas em português.

Fluxo:
  1. normalizar(texto)               -> minúsculo, sem acento, sem pontuação
  2. substituir_numeros_por_digitos  -> "treze quatro a sete" -> "13 4 a 7"
  3. localizar_livro                 -> encontra o alias de livro mais longo
                                          que aparece no texto (evita que
                                          "joao" capture dentro de "1 joao")
  4. extrair capítulo / versículo(s) a partir dos números que vêm logo
     depois do nome do livro

Retorna objetos ReferenciaDetectada com um campo `confianca` (0-1) baseado
em quão "limpo" foi o casamento (livro + capítulo + versículo todos
presentes = confiança alta; só livro + capítulo = confiança média).

Em ambiente de culto ao vivo, o chamador deve exigir confiança mínima
(ex: >= 0.6) e, mesmo assim, sempre passar pela camada de confirmação
antes de exibir (ver especificação da Fase 2 / camada de confirmação).
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional

from biblia_livros import LIVROS, SINGLE_CHAPTER_BOOKS
from numeros_pt import substituir_numeros_por_digitos

PALAVRAS_RANGE = {"a", "ate", "até"}
PALAVRAS_IGNORAR_APOS_LIVRO = {
    "capitulo", "capítulo", "versiculo", "versiculos", "versículo",
    "versículos", "verso", "versos", "cap", "v", "vv",
}


@dataclass
class ReferenciaDetectada:
    livro: str
    capitulo: int
    versiculo_inicio: Optional[int] = None
    versiculo_fim: Optional[int] = None
    confianca: float = 0.0
    texto_original: str = ""
    trecho_casado: str = ""

    def referencia_formatada(self) -> str:
        """Formato tipo Holyrics: 'Livro cap:vers' ou 'Livro cap:vers-fim'."""
        if self.versiculo_inicio is None:
            return f"{self.livro} {self.capitulo}"
        if self.versiculo_fim and self.versiculo_fim != self.versiculo_inicio:
            return f"{self.livro} {self.capitulo}:{self.versiculo_inicio}-{self.versiculo_fim}"
        return f"{self.livro} {self.capitulo}:{self.versiculo_inicio}"


def _remover_acentos(s: str) -> str:
    nfkd = unicodedata.normalize("NFKD", s)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def normalizar(texto: str) -> str:
    texto = texto.lower()
    texto = _remover_acentos(texto)
    # normaliza pontuação comum de STT em separador de espaço
    texto = re.sub(r"[.,;:!?()\[\]\"']", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


# Constrói índice alias -> nome canônico, ordenado por número de palavras
# do alias (decrescente) para casar sempre o alias mais específico primeiro
# (ex: "1 joao" antes de "joao").
_ALIAS_INDEX = []
for nome_canonico, dados in LIVROS.items():
    for alias in dados["aliases"]:
        alias_norm = normalizar(alias)
        _ALIAS_INDEX.append((alias_norm, nome_canonico))
_ALIAS_INDEX.sort(key=lambda x: len(x[0].split()), reverse=True)


def _localizar_livro(texto_norm: str):
    """
    Procura no texto normalizado (sem números convertidos ainda, pois
    aliases como '1 corintios' dependem do dígito) o alias de livro mais
    longo que aparece, com fronteiras de palavra.
    Retorna (nome_canonico, span_inicio, span_fim) ou None.
    """
    melhor = None
    for alias, canonico in _ALIAS_INDEX:
        # \b não funciona bem com acento removido + números, usamos
        # fronteiras manuais via regex de espaço/início/fim de string
        pattern = r"(?<!\w)" + re.escape(alias) + r"(?!\w)"
        m = re.search(pattern, texto_norm)
        if m:
            # prioriza o alias mais longo (mais específico); como já está
            # ordenado por tamanho, o primeiro achado é o melhor
            melhor = (canonico, m.start(), m.end())
            break
    return melhor


def _extrair_numeros_apos(texto_norm: str, pos_fim_livro: int):
    """
    A partir da posição logo após o nome do livro, extrai até 2 números
    (capítulo e verso_inicio) e opcionalmente um terceiro (verso_fim, se
    precedido de 'a'/'até'). Ignora palavras de enchimento como
    'capitulo', 'versiculo', 'verso'.
    """
    resto = texto_norm[pos_fim_livro:].strip()
    tokens = resto.split()

    numeros = []
    tem_range = False
    i = 0
    while i < len(tokens) and len(numeros) < 3:
        tok = tokens[i]
        if tok in PALAVRAS_IGNORAR_APOS_LIVRO:
            i += 1
            continue
        if tok in PALAVRAS_RANGE:
            tem_range = True
            i += 1
            continue
        if re.fullmatch(r"\d{1,3}", tok):
            numeros.append(int(tok))
            i += 1
            continue
        # qualquer outra palavra encerra a leitura de números
        # (ex: começou a próxima frase / outro assunto)
        break

    return numeros, tem_range


def parse_referencia(texto: str) -> List[ReferenciaDetectada]:
    """
    Ponto de entrada principal. Recebe a transcrição (bruta, do STT) de uma
    janela de fala e retorna 0 ou mais ReferenciaDetectada encontradas.

    Suporta múltiplas referências na mesma frase (ex: "leiam Romanos 8 e
    depois Filipenses 4") fazendo varredura iterativa — mas o uso típico
    em culto é 1 referência por vez.
    """
    if not texto or not texto.strip():
        return []

    texto_norm = normalizar(texto)
    texto_num = substituir_numeros_por_digitos(texto_norm)

    resultados = []
    cursor = 0
    texto_restante = texto_num

    while True:
        achado = _localizar_livro(texto_restante)
        if not achado:
            break
        livro, ini, fim = achado
        numeros, tem_range = _extrair_numeros_apos(texto_restante, fim)

        capitulo = None
        v_ini = None
        v_fim = None
        confianca = 0.0

        if livro in SINGLE_CHAPTER_BOOKS:
            capitulo = 1
            if numeros:
                v_ini = numeros[0]
                confianca = 0.85
                if tem_range and len(numeros) >= 2:
                    v_fim = numeros[1]
            else:
                confianca = 0.5  # só o nome do livro, sem versículo
        else:
            if len(numeros) >= 1:
                capitulo = numeros[0]
                confianca = 0.55  # só capítulo
            if len(numeros) >= 2:
                v_ini = numeros[1]
                confianca = 0.9  # capítulo + versículo = alta confiança
            if tem_range and len(numeros) >= 3:
                v_fim = numeros[2]
                confianca = 0.95

        if capitulo is not None:
            resultados.append(
                ReferenciaDetectada(
                    livro=livro,
                    capitulo=capitulo,
                    versiculo_inicio=v_ini,
                    versiculo_fim=v_fim,
                    confianca=confianca,
                    texto_original=texto,
                    trecho_casado=texto_restante[ini:fim],
                )
            )

        # avança o cursor pra procurar outra referência na mesma frase
        avanco = fim
        if numeros:
            # pula os tokens numéricos já consumidos, aproximação simples:
            # avança até o fim do trecho onde os números foram encontrados
            resto = texto_restante[fim:]
            m = re.search(r"(\d[\d\s\w]*?)(?=\s\D|$)", resto)
            avanco = fim + (m.end() if m else 0)
        texto_restante = texto_restante[avanco:] if avanco > 0 else texto_restante[fim:]
        if not texto_restante.strip():
            break

    return resultados


if __name__ == "__main__":
    testes = [
        "Gênesis 3:11",
        "Gênesis três onze",
        "primeira de coríntios treze, quatro a sete",
        "primeira coríntios treze quatro a sete",
        "Salmo 23",
        "João três dezesseis",
        "vamos ler em Romanos oito, versículo vinte e oito",
        "Filemom versículo seis",
        "leiam também Judas versículo três",
        "segunda de Timóteo três dezesseis a dezessete",
        "Salmo cento e dezenove, versículo cento e cinco",
        "Apocalipse vinte e um, quatro",
        "isso não é uma referência bíblica de jeito nenhum",
    ]

    for t in testes:
        refs = parse_referencia(t)
        print(f"\nEntrada: {t!r}")
        if not refs:
            print("  -> nenhuma referência detectada")
        for r in refs:
            print(
                f"  -> {r.referencia_formatada()}  "
                f"(confiança={r.confianca:.2f}, trecho={r.trecho_casado!r})"
            )
