# -*- coding: utf-8 -*-
"""
Lista os dispositivos de áudio de entrada disponíveis no sistema.

Rode isso primeiro, com a interface USB (ligada no Aux/Matrix Out da X32)
já conectada, pra descobrir o índice/nome exato do dispositivo que vamos
usar em captura_audio.py.

Uso:
    python listar_dispositivos.py
"""

import sounddevice as sd


def listar_entradas():
    print("Dispositivos de áudio disponíveis:\n")
    dispositivos = sd.query_devices()
    for i, d in enumerate(dispositivos):
        if d["max_input_channels"] > 0:
            marcador = " <-- padrão" if i == sd.default.device[0] else ""
            print(
                f"  [{i}] {d['name']}"
                f"  (canais de entrada: {d['max_input_channels']}, "
                f"taxa padrão: {int(d['default_samplerate'])} Hz){marcador}"
            )
    print(
        "\nAnote o número [i] da interface USB ligada na saída "
        "Aux/Matrix da X32 — você vai usar esse índice em captura_audio.py "
        "(variável DEVICE_INDEX)."
    )


if __name__ == "__main__":
    listar_entradas()
