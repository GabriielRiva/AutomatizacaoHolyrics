# -*- coding: utf-8 -*-
"""
Script de diagnóstico pra descobrir por que o Holyrics está retornando
"Item not found" no ShowVerse.

Uso:
    export HOLYRICS_TOKEN="seu_token_aqui"   (ou $env: no PowerShell)
    python diagnostico_holyrics.py
"""

import os
from holyrics_client import HolyricsClient, HolyricsAPIError

TOKEN = os.environ.get("HOLYRICS_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")

cliente = HolyricsClient(token=TOKEN)

print("=" * 60)
print("1) Testando conexão básica...")
try:
    cliente.testar_conexao()
    print("   OK — conexão e token funcionando.")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")
    raise SystemExit(1)

print("\n" + "=" * 60)
print("2) Listando versões da bíblia instaladas...")
try:
    versoes = cliente.listar_versoes_biblia()
    print(f"   Resposta crua: {versoes}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("3) Testando ShowVerse por TEXTO (não por ID), com 'pt_nvi'...")
try:
    resultado = cliente.exibir_versiculo("Gênesis 3:1", versao="pt_nvi")
    print(f"   OK: {resultado}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("4) Testando ShowVerse por TEXTO, sem especificar versão...")
try:
    payload_sem_versao = cliente._chamar(
        "ShowVerse", {"input": {"references": "Gênesis 3:1"}}
    )
    print(f"   OK: {payload_sem_versao}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("5) Testando ShowVerse por ID numérico (01003001 = Gênesis 3:1)...")
try:
    resultado = cliente._chamar(
        "ShowVerse", {"input": {"id": "01003001"}, "version": "pt_nvi"}
    )
    print(f"   OK: {resultado}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("Diagnóstico concluído. Cole a saída completa de volta na conversa.")
