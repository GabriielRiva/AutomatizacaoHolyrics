# -*- coding: utf-8 -*-
"""
Captura de áudio contínua (streaming) a partir da interface USB ligada no
Aux/Matrix Out da X32, transcreve em português com Vosk (offline) e passa
cada frase reconhecida pro parser de referências bíblicas.

ANTES DE RODAR:
  1. pip install vosk sounddevice scipy
  2. Baixe o modelo de português do Vosk em:
     https://alphacephei.com/vosk/models
     Recomendado pra começar: "vosk-model-small-pt-0.3" (~50 MB, mais
     rápido, boa precisão pra frases curtas tipo referência bíblica).
     Se notar muitos erros de reconhecimento, migre depois pro
     "vosk-model-pt-fb-v0.1.1-20220516_2113" (maior e mais preciso).
  3. Descompacte o modelo numa pasta e ajuste MODEL_PATH abaixo.
  4. Rode antes: python listar_dispositivos.py
     e ajuste DEVICE_INDEX com o índice da interface USB da X32.

COMO FUNCIONA:
  - Thread de captura (callback do sounddevice) só empilha os blocos de
    áudio numa fila — não faz processamento pesado ali, pra não perder
    amostras.
  - Thread principal consome a fila, alimenta o KaldiRecognizer do Vosk.
  - Quando o Vosk fecha uma frase (resultado "final", não parcial),
    mandamos o texto pro parse_referencia().
  - Se uma referência com confiança >= LIMIAR_CONFIANCA for encontrada,
    ela é impressa como candidata — a exibição real no Holyrics só deve
    acontecer depois da camada de confirmação humana (próxima etapa do
    projeto, ainda não implementada aqui).
"""

import json
import queue
import sys

import numpy as np
import sounddevice as sd
from vosk import KaldiRecognizer, Model

from parser_referencias import parse_referencia

# ----------------------- CONFIGURAÇÃO -----------------------
MODEL_PATH = "modelo_vosk_pt"          # pasta onde você descompactou o modelo
DEVICE_INDEX = None                     # None = dispositivo padrão do sistema;
                                         # troque pelo índice da interface USB
                                         # (veja listar_dispositivos.py)
SAMPLE_RATE_VOSK = 16000                # taxa que o Vosk espera
BLOCO_MS = 250                          # tamanho de cada bloco de captura
LIMIAR_CONFIANCA = 0.6                  # abaixo disso, nem mostramos candidata
# --------------------------------------------------------------

fila_audio = queue.Queue()


def callback_audio(indata, frames, time_info, status):
    """Chamado pelo PortAudio em thread separada a cada bloco capturado.
    Deve ser rápido e nunca bloquear — só empilha os dados."""
    if status:
        print(f"[aviso audio] {status}", file=sys.stderr)
    fila_audio.put(bytes(indata))


def _taxa_suportada(device_index, taxa_desejada):
    """Verifica se o dispositivo aceita capturar diretamente na taxa
    desejada (evita precisar reamostrar depois)."""
    try:
        sd.check_input_settings(
            device=device_index, samplerate=taxa_desejada, channels=1
        )
        return True
    except Exception:
        return False


def iniciar_captura():
    print("Carregando modelo Vosk...")
    modelo = Model(MODEL_PATH)
    reconhecedor = KaldiRecognizer(modelo, SAMPLE_RATE_VOSK)
    reconhecedor.SetWords(False)

    device_info = sd.query_devices(DEVICE_INDEX, "input")
    print(f"Dispositivo de entrada: {device_info['name']}")

    if _taxa_suportada(DEVICE_INDEX, SAMPLE_RATE_VOSK):
        taxa_captura = SAMPLE_RATE_VOSK
        print(f"Capturando diretamente em {SAMPLE_RATE_VOSK} Hz.")
    else:
        taxa_captura = int(device_info["default_samplerate"])
        print(
            f"Dispositivo não suporta {SAMPLE_RATE_VOSK} Hz diretamente. "
            f"Capturando em {taxa_captura} Hz e reamostrando em tempo real."
        )

    bloco_frames = int(taxa_captura * BLOCO_MS / 1000)

    with sd.RawInputStream(
        samplerate=taxa_captura,
        blocksize=bloco_frames,
        device=DEVICE_INDEX,
        dtype="int16",
        channels=1,
        callback=callback_audio,
    ):
        print("\nEscutando... (Ctrl+C pra parar)\n")
        while True:
            dados = fila_audio.get()

            if taxa_captura != SAMPLE_RATE_VOSK:
                dados = _reamostrar(dados, taxa_captura, SAMPLE_RATE_VOSK)

            if reconhecedor.AcceptWaveform(dados):
                resultado = json.loads(reconhecedor.Result())
                texto = resultado.get("text", "").strip()
                if texto:
                    processar_texto_reconhecido(texto)
            # resultados parciais (reconhecedor.PartialResult()) podem ser
            # usados futuramente pra feedback visual "ouvindo..." em tempo
            # real, mas não devem disparar detecção de referência ainda,
            # pois o texto pode mudar até a frase fechar.


def _reamostrar(pcm_bytes, taxa_origem, taxa_destino):
    """Reamostra um bloco de áudio PCM int16 mono de taxa_origem pra
    taxa_destino usando scipy (qualidade boa o suficiente pra fala)."""
    from scipy.signal import resample_poly
    from math import gcd

    audio = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
    g = gcd(taxa_destino, taxa_origem)
    up = taxa_destino // g
    down = taxa_origem // g
    reamostrado = resample_poly(audio, up, down)
    return reamostrado.astype(np.int16).tobytes()


def processar_texto_reconhecido(texto):
    print(f"[reconhecido] {texto}")
    referencias = parse_referencia(texto)
    for ref in referencias:
        if ref.confianca >= LIMIAR_CONFIANCA:
            print(
                f"  >>> CANDIDATA: {ref.referencia_formatada()} "
                f"(confiança={ref.confianca:.2f}) "
                f"-- aguardando confirmação humana"
            )
        else:
            print(
                f"  (descartado, confiança baixa: "
                f"{ref.referencia_formatada()} = {ref.confianca:.2f})"
            )


if __name__ == "__main__":
    try:
        iniciar_captura()
    except KeyboardInterrupt:
        print("\nCaptura interrompida.")
    except Exception as e:
        print(f"\nErro: {e}")
        print(
            "\nDicas:\n"
            "  - Confirme que MODEL_PATH aponta pra pasta do modelo Vosk "
            "descompactado.\n"
            "  - Rode 'python listar_dispositivos.py' e confirme "
            "DEVICE_INDEX.\n"
            "  - Confirme que 'pip install vosk sounddevice scipy' rodou "
            "sem erro."
        )
