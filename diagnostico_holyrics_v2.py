# -*- coding: utf-8 -*-
"""
Diagnóstico v2 — roda depois de setar HOLYRICS_TOKEN no mesmo terminal.
"""

import os
import json
from holyrics_client import HolyricsClient, HolyricsAPIError

TOKEN = os.environ.get("HOLYRICS_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
cliente = HolyricsClient(token=TOKEN)

print("=" * 60)
print("A) Listando TODAS as versões instaladas (procurando 'pt' / português)...")
try:
    versoes = cliente.listar_versoes_biblia()
    portugues = [v for v in versoes if v.get("language", {}).get("id") == "pt"]
    print(f"   Total de versões instaladas: {len(versoes)}")
    print(f"   Versões em português encontradas: {portugues}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")
    portugues = []

if not portugues:
    print("\n   NENHUMA versão em português foi encontrada na instalação!")
    print("   -> Você precisa instalar uma bíblia em português no Holyrics")
    print("      (dentro do próprio app: Bíblia > Gerenciar Versões, ou")
    print("      similar, dependendo da versão do Holyrics).")
    raise SystemExit(0)

chave_pt = portugues[0]["key"]
print(f"\n   Vou usar a chave '{chave_pt}' nos próximos testes.")

print("\n" + "=" * 60)
print(f"B) ShowVerse por texto simples, sem acento, versão='{chave_pt}'...")
try:
    r = cliente._chamar("ShowVerse", {
        "input": {"references": "Genesis 3:1"},
        "version": chave_pt,
    })
    print(f"   OK: {r}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print(f"C) ShowVerse por texto 'Gn 3:1' (abreviação), versão='{chave_pt}'...")
try:
    r = cliente._chamar("ShowVerse", {
        "input": {"references": "Gn 3:1"},
        "version": chave_pt,
    })
    print(f"   OK: {r}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print(f"D) ShowVerse por ID '01001001' (Gênesis 1:1), versão='{chave_pt}'...")
try:
    r = cliente._chamar("ShowVerse", {
        "input": {"id": "01001001"},
        "version": chave_pt,
    })
    print(f"   OK: {r}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("E) GetCPInfo (info do estado atual, sem tentar exibir nada)...")
try:
    r = cliente.info_apresentacao_atual()
    print(f"   OK: {r}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("F) CheckToken — permissões do token atual...")
try:
    r = cliente.checar_permissoes(["ShowVerse", "GetBibleVersions", "GetCPInfo"])
    print(f"   OK: {r}")
except HolyricsAPIError as e:
    print(f"   FALHOU: {e}")

print("\n" + "=" * 60)
print("Cole a saída completa (do A ao F) de volta na conversa.")
