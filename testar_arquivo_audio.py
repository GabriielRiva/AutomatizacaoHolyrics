# -*- coding: utf-8 -*-
"""
Testa o pipeline Vosk + parser usando um ARQUIVO de áudio já gravado,
em vez de captura ao vivo por microfone. Útil pra testar em qualquer
lugar (ex: gravar um áudio no celular dizendo uma referência bíblica,
transferir pro PC, e rodar contra este script).

REQUISITOS DO ARQUIVO:
  - Formato WAV
  - Mono (1 canal)
  - PCM 16-bit
  - Taxa de amostragem: idealmente 16000 Hz (mas o script reamostra
    automaticamente se vier em outra taxa, ex: 44100/48000 do celular)

Se você gravou em outro formato (ex: m4a do WhatsApp/iPhone, ou mp3),
converta pra WAV primeiro. O jeito mais simples é com o ffmpeg:
    ffmpeg -i audio_original.m4a -ar 16000 -ac 1 -sample_fmt s16 teste.wav

Uso:
    python testar_arquivo_audio.py teste.wav
"""

import json
import sys
import wave

from vosk import KaldiRecognizer, Model

from parser_referencias import parse_referencia

MODEL_PATH = "modelo_vosk_pt"
LIMIAR_CONFIANCA = 0.6


def _reamostrar_se_necessario(wf):
    """Se o WAV não estiver em 16kHz mono 16-bit, reamostra usando scipy
    e devolve os bytes PCM prontos + a taxa final (sempre 16000)."""
    taxa = wf.getframerate()
    canais = wf.getnchannels()
    largura = wf.getsampwidth()

    frames = wf.readframes(wf.getnframes())

    import numpy as np

    if largura != 2:
        raise ValueError(
            f"O WAV precisa ser PCM 16-bit (sampwidth=2). "
            f"Este arquivo tem sampwidth={largura}. Reexporte em 16-bit."
        )

    audio = np.frombuffer(frames, dtype=np.int16)

    if canais > 1:
        # downmix simples pra mono, pegando a média dos canais
        audio = audio.reshape(-1, canais).mean(axis=1).astype(np.int16)

    if taxa != 16000:
        from scipy.signal import resample_poly
        from math import gcd

        g = gcd(16000, taxa)
        up, down = 16000 // g, taxa // g
        audio = resample_poly(audio.astype(np.float32), up, down).astype(np.int16)

    return audio.tobytes()


def testar_arquivo(caminho_wav):
    print(f"Carregando modelo Vosk de '{MODEL_PATH}'...")
    modelo = Model(MODEL_PATH)
    reconhecedor = KaldiRecognizer(modelo, 16000)

    print(f"Lendo áudio de '{caminho_wav}'...")
    with wave.open(caminho_wav, "rb") as wf:
        print(
            f"  formato original: {wf.getframerate()} Hz, "
            f"{wf.getnchannels()} canal(is), {wf.getsampwidth()*8}-bit"
        )
        pcm = _reamostrar_se_necessario(wf)

    # alimenta o reconhecedor em blocos, simulando streaming
    tamanho_bloco = 8000  # bytes por bloco (~0.25s em 16kHz 16-bit mono)
    textos_finais = []

    for inicio in range(0, len(pcm), tamanho_bloco):
        bloco = pcm[inicio: inicio + tamanho_bloco]
        if reconhecedor.AcceptWaveform(bloco):
            resultado = json.loads(reconhecedor.Result())
            texto = resultado.get("text", "").strip()
            if texto:
                textos_finais.append(texto)

    resultado_final = json.loads(reconhecedor.FinalResult())
    texto_final = resultado_final.get("text", "").strip()
    if texto_final:
        textos_finais.append(texto_final)

    print("\n--- Transcrição ---")
    if not textos_finais:
        print("(nenhum texto reconhecido — áudio vazio, silencioso, ou "
              "muito diferente do que o modelo espera)")
        return

    for texto in textos_finais:
        print(f"  \"{texto}\"")
        referencias = parse_referencia(texto)
        if not referencias:
            print("    -> nenhuma referência bíblica detectada nesse trecho")
            continue
        for ref in referencias:
            status = "CANDIDATA" if ref.confianca >= LIMIAR_CONFIANCA else "descartada (confiança baixa)"
            print(
                f"    -> {status}: {ref.referencia_formatada()} "
                f"(confiança={ref.confianca:.2f})"
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python testar_arquivo_audio.py caminho_do_audio.wav")
        sys.exit(1)

    try:
        testar_arquivo(sys.argv[1])
    except FileNotFoundError as e:
        print(f"Erro: arquivo não encontrado. {e}")
    except Exception as e:
        print(f"Erro: {e}")
        print(
            "\nDicas:\n"
            "  - Confirme que o modelo Vosk está em 'modelo_vosk_pt/' "
            "na pasta do projeto.\n"
            "  - Confirme que o arquivo é WAV PCM 16-bit (use ffmpeg pra "
            "converter se necessário — veja instruções no topo do arquivo)."
        )
