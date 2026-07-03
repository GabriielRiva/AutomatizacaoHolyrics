# -*- coding: utf-8 -*-
"""
Protótipo da camada de confirmação — versão de CONSOLE (texto), só pra
validar o fluxo completo parser -> confirmação -> Holyrics antes de
construir a interface gráfica de verdade.

REGRA DE OURO deste sistema: NUNCA exibir automaticamente. Toda
candidata detectada passa por aqui e espera confirmação explícita do
operador antes de qualquer chamada ao Holyrics.

Uso interativo (digite frases como se fosse a transcrição do STT):
    python confirmar_e_exibir.py

Uso não-interativo, testando uma frase específica direto:
    python confirmar_e_exibir.py "Salmo vinte e três"
"""

import sys

from parser_referencias import parse_referencia
from holyrics_client import HolyricsClient, HolyricsAPIError

TOKEN = "COLOQUE_SEU_TOKEN_AQUI"
LIMIAR_CONFIANCA = 0.6


def confirmar_no_console(ref):
    """
    Mostra a referência candidata e pede confirmação explícita.
    Retorna True se confirmado, False se recusado/cancelado.

    Esta é a versão texto do que depois vira uma janela popup — a
    lógica de "nunca prosseguir sem resposta explícita" é a mesma.
    """
    print("\n" + "=" * 50)
    print(f"  REFERÊNCIA DETECTADA: {ref.referencia_formatada()}")
    print(f"  Confiança: {ref.confianca:.0%}")
    print(f"  (transcrição original: \"{ref.texto_original}\")")
    print("=" * 50)
    resposta = input("  Exibir? [S]im / [n]ão: ").strip().lower()
    return resposta in ("", "s", "sim", "y", "yes")


def processar_frase(texto, cliente):
    referencias = parse_referencia(texto)

    if not referencias:
        print(f'  (nenhuma referência detectada em: "{texto}")')
        return

    for ref in referencias:
        if ref.confianca < LIMIAR_CONFIANCA:
            print(
                f"  (descartada por confiança baixa: "
                f"{ref.referencia_formatada()} = {ref.confianca:.2f})"
            )
            continue

        if confirmar_no_console(ref):
            try:
                cliente.exibir_por_referencia_detectada(ref)
                print(f"  ✔ Exibido no Holyrics: {ref.referencia_formatada()}")
            except HolyricsAPIError as e:
                print(f"  ✘ Erro ao exibir no Holyrics: {e}")
        else:
            print("  Cancelado pelo operador.")


def main():
    cliente = HolyricsClient(token=TOKEN)

    print("Verificando conexão com o Holyrics...")
    try:
        cliente.testar_conexao()
        print("Conexão OK.\n")
    except HolyricsAPIError as e:
        print(f"AVISO: não foi possível conectar ao Holyrics ({e})")
        print("Continuando mesmo assim — você verá as candidatas, mas "
              "a exibição real vai falhar até a conexão ser corrigida.\n")

    # Modo não-interativo: frase passada como argumento de linha de comando
    if len(sys.argv) > 1:
        texto = " ".join(sys.argv[1:])
        processar_frase(texto, cliente)
        return

    # Modo interativo: simula o fluxo de streaming, uma frase por vez
    print("Digite frases (como se fossem transcrições do STT).")
    print("Digite 'sair' para encerrar.\n")
    while True:
        texto = input("Frase transcrita > ").strip()
        if texto.lower() in ("sair", "exit", "quit"):
            break
        if not texto:
            continue
        processar_frase(texto, cliente)


if __name__ == "__main__":
    main()
