# -*- coding: utf-8 -*-
"""
Sistema completo com PAINEL DE CONTROLE gráfico.

Diferença em relação à versão anterior: a captura de áudio NÃO começa
sozinha quando o programa abre. Existe uma janela principal com um
botão "Iniciar Captura" / "Parar Captura", pra você controlar
exatamente quando o sistema começa a escutar (ex: só quando o culto
realmente começar) e quando parar (ex: durante avisos, oferta, etc.,
se quiser evitar detecções nesses momentos).

ARQUITETURA:
  - O modelo Vosk é carregado UMA VEZ, em segundo plano, assim que o
    programa abre (carregar o modelo demora alguns segundos — melhor
    fazer isso enquanto você ainda está de preparação, não na hora H).
  - O botão "Iniciar Captura" só fica habilitado depois que o modelo
    termina de carregar.
  - Cada clique em "Iniciar" cria uma nova thread de captura de áudio;
    "Parar" sinaliza essa thread pra encerrar e fechar o stream.
  - A janela principal tem um log visual das transcrições e detecções,
    então o operador não precisa olhar o terminal durante o culto.

ANTES DE RODAR:
  1. Ajuste as constantes de configuração logo abaixo.
  2. Tenha o Holyrics aberto com o API Server ativado.
  3. python sistema_completo.py
"""

import json
import os
import queue
import sys
import threading
import tkinter as tk
from tkinter import scrolledtext
from datetime import datetime

import sounddevice as sd
from vosk import KaldiRecognizer, Model

from parser_referencias import parse_referencia
from janela_confirmacao import JanelaConfirmacao
from holyrics_client import HolyricsClient, HolyricsAPIError

# ----------------------- CONFIGURAÇÃO -----------------------
# NUNCA deixe o token real commitado no git. Configure a variável de
# ambiente HOLYRICS_TOKEN antes de rodar, por exemplo:
#   Windows (PowerShell):  $env:HOLYRICS_TOKEN = "seu_token_aqui"
#   Windows (cmd):         set HOLYRICS_TOKEN=seu_token_aqui
#   Linux/Mac:              export HOLYRICS_TOKEN=seu_token_aqui
# Ou crie um arquivo config_local.py (já no .gitignore) com:
#   HOLYRICS_TOKEN = "seu_token_aqui"
# e troque a linha abaixo por: from config_local import HOLYRICS_TOKEN
HOLYRICS_TOKEN = os.environ.get("HOLYRICS_TOKEN", "COLOQUE_SEU_TOKEN_AQUI")
HOLYRICS_IP = "127.0.0.1"
HOLYRICS_PORTA = 8091
HOLYRICS_VERSAO_BIBLIA = "pt_nvi"   # NVI — troque se sua igreja usar outra

MODEL_PATH = "modelo_vosk_pt"
DEVICE_INDEX = None              # None = dispositivo padrão do sistema
SAMPLE_RATE_VOSK = 16000
BLOCO_MS = 250

LIMIAR_CONFIANCA = 0.6
TIMEOUT_CONFIRMACAO_SEGUNDOS = 12
# --------------------------------------------------------------


class SistemaVersiculos:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Versículos — Painel de Controle")
        self.root.geometry("620x460")
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self.modelo_vosk = None
        self.thread_captura = None
        self.evento_parar = None
        self.capturando = False
        self.contador_confirmados = 0

        self.cliente_holyrics = HolyricsClient(
            token=HOLYRICS_TOKEN, ip=HOLYRICS_IP, port=HOLYRICS_PORTA,
            versao_padrao=HOLYRICS_VERSAO_BIBLIA,
        )

        self.gerenciador_janela = JanelaConfirmacao(
            self.root,
            ao_confirmar=self._ao_confirmar,
            ao_cancelar=self._ao_cancelar,
            timeout_segundos=TIMEOUT_CONFIRMACAO_SEGUNDOS,
        )

        self._montar_interface()
        self._verificar_holyrics_em_thread()
        self._carregar_modelo_em_thread()

    # ---------------------- INTERFACE ----------------------

    def _montar_interface(self):
        tk.Label(
            self.root, text="Sistema de Versículos", font=("Segoe UI", 18, "bold"),
            fg="#ffffff", bg="#1a1a2e",
        ).pack(pady=(20, 5))

        self.rotulo_status = tk.Label(
            self.root, text="● Carregando modelo de voz...",
            font=("Segoe UI", 12, "bold"), fg="#ccaa44", bg="#1a1a2e",
        )
        self.rotulo_status.pack(pady=(0, 5))

        self.rotulo_holyrics = tk.Label(
            self.root, text="Holyrics: verificando conexão...",
            font=("Segoe UI", 9), fg="#8888aa", bg="#1a1a2e",
        )
        self.rotulo_holyrics.pack(pady=(0, 15))

        self.botao_iniciar = tk.Button(
            self.root, text="▶ Iniciar Captura", font=("Segoe UI", 13, "bold"),
            bg="#2d7d46", fg="white", activebackground="#3a9d5a",
            width=22, height=2, relief="flat", cursor="hand2",
            state="disabled", command=self._alternar_captura,
        )
        self.botao_iniciar.pack(pady=(0, 15))

        tk.Label(
            self.root, text="Log de atividade:", font=("Segoe UI", 10, "bold"),
            fg="#8888aa", bg="#1a1a2e", anchor="w",
        ).pack(fill="x", padx=20)

        self.caixa_log = scrolledtext.ScrolledText(
            self.root, height=14, font=("Consolas", 9),
            bg="#0f0f1a", fg="#cccccc", insertbackground="white",
            relief="flat",
        )
        self.caixa_log.pack(fill="both", expand=True, padx=20, pady=(5, 10))
        self.caixa_log.configure(state="disabled")

        self.rotulo_rodape = tk.Label(
            self.root, text="Versículos exibidos nesta sessão: 0",
            font=("Segoe UI", 9), fg="#666688", bg="#1a1a2e",
        )
        self.rotulo_rodape.pack(pady=(0, 10))

    def _log(self, texto):
        """Thread-safe: sempre agenda a escrita no widget pra thread
        principal via root.after."""
        def escrever():
            hora = datetime.now().strftime("%H:%M:%S")
            self.caixa_log.configure(state="normal")
            self.caixa_log.insert("end", f"[{hora}] {texto}\n")
            self.caixa_log.see("end")
            self.caixa_log.configure(state="disabled")

        self.root.after(0, escrever)

    # ---------------------- HOLYRICS ----------------------

    def _verificar_holyrics_em_thread(self):
        def alvo():
            try:
                self.cliente_holyrics.testar_conexao()
                self.root.after(0, lambda: self.rotulo_holyrics.config(
                    text="Holyrics: conectado ✔", fg="#66aa66"))
            except HolyricsAPIError as e:
                self.root.after(0, lambda: self.rotulo_holyrics.config(
                    text="Holyrics: sem conexão ✘ (verifique se está aberto)",
                    fg="#cc6666"))
                self._log(f"Aviso: Holyrics não conectado ({e})")

        threading.Thread(target=alvo, daemon=True).start()

    # ---------------------- CARREGAR MODELO ----------------------

    def _carregar_modelo_em_thread(self):
        def alvo():
            try:
                self.modelo_vosk = Model(MODEL_PATH)
                self.root.after(0, self._modelo_pronto)
            except Exception as e:
                self.root.after(0, lambda: self.rotulo_status.config(
                    text="● Erro ao carregar modelo Vosk", fg="#cc6666"))
                self._log(f"ERRO ao carregar modelo Vosk: {e}")
                self._log(f"Confirme que a pasta '{MODEL_PATH}' contém o "
                          f"modelo descompactado.")

        threading.Thread(target=alvo, daemon=True).start()

    def _modelo_pronto(self):
        self.rotulo_status.config(text="● Pronto (parado)", fg="#8888aa")
        self.botao_iniciar.config(state="normal")
        self._log("Modelo de voz carregado. Pronto pra iniciar captura.")

    # ---------------------- CAPTURA ----------------------

    def _alternar_captura(self):
        if self.capturando:
            self._parar_captura()
        else:
            self._iniciar_captura()

    def _iniciar_captura(self):
        self.evento_parar = threading.Event()
        self.thread_captura = threading.Thread(
            target=self._loop_reconhecimento, args=(self.evento_parar,),
            daemon=True,
        )
        self.thread_captura.start()
        self.capturando = True
        self.botao_iniciar.config(text="■ Parar Captura", bg="#a13d3d",
                                   activebackground="#c14d4d")
        self.rotulo_status.config(text="● Escutando...", fg="#66aa66")
        self._log("Captura iniciada.")

    def _parar_captura(self):
        if self.evento_parar:
            self.evento_parar.set()
        self.capturando = False
        self.botao_iniciar.config(text="▶ Iniciar Captura", bg="#2d7d46",
                                   activebackground="#3a9d5a")
        self.rotulo_status.config(text="● Pronto (parado)", fg="#8888aa")
        self._log("Captura parada.")

    def _loop_reconhecimento(self, evento_parar):
        reconhecedor = KaldiRecognizer(self.modelo_vosk, SAMPLE_RATE_VOSK)
        reconhecedor.SetWords(False)
        fila_local = queue.Queue()

        def callback_audio(indata, frames, time_info, status):
            if status:
                print(f"[aviso audio] {status}", file=sys.stderr)
            fila_local.put(bytes(indata))

        try:
            device_info = sd.query_devices(DEVICE_INDEX, "input")
        except Exception as e:
            self._log(f"ERRO ao acessar dispositivo de áudio: {e}")
            self.root.after(0, self._parar_captura)
            return

        if self._taxa_suportada(SAMPLE_RATE_VOSK):
            taxa_captura = SAMPLE_RATE_VOSK
        else:
            taxa_captura = int(device_info["default_samplerate"])
            self._log(f"Capturando em {taxa_captura} Hz, reamostrando "
                      f"pra {SAMPLE_RATE_VOSK} Hz")

        bloco_frames = int(taxa_captura * BLOCO_MS / 1000)

        try:
            stream = sd.RawInputStream(
                samplerate=taxa_captura, blocksize=bloco_frames,
                device=DEVICE_INDEX, dtype="int16", channels=1,
                callback=callback_audio,
            )
        except Exception as e:
            self._log(f"ERRO ao abrir stream de áudio: {e}")
            self.root.after(0, self._parar_captura)
            return

        with stream:
            while not evento_parar.is_set():
                try:
                    dados = fila_local.get(timeout=0.5)
                except queue.Empty:
                    continue

                if taxa_captura != SAMPLE_RATE_VOSK:
                    dados = self._reamostrar(dados, taxa_captura, SAMPLE_RATE_VOSK)

                if reconhecedor.AcceptWaveform(dados):
                    resultado = json.loads(reconhecedor.Result())
                    texto = resultado.get("text", "").strip()
                    if texto:
                        self._processar_texto(texto)

    def _taxa_suportada(self, taxa_desejada):
        try:
            sd.check_input_settings(device=DEVICE_INDEX, samplerate=taxa_desejada, channels=1)
            return True
        except Exception:
            return False

    def _reamostrar(self, pcm_bytes, taxa_origem, taxa_destino):
        import numpy as np
        from scipy.signal import resample_poly
        from math import gcd

        audio = np.frombuffer(pcm_bytes, dtype="int16").astype("float32")
        g = gcd(taxa_destino, taxa_origem)
        up, down = taxa_destino // g, taxa_origem // g
        reamostrado = resample_poly(audio, up, down)
        return reamostrado.astype("int16").tobytes()

    def _processar_texto(self, texto):
        self._log(f"Reconhecido: \"{texto}\"")
        referencias = parse_referencia(texto)
        for ref in referencias:
            if ref.confianca >= LIMIAR_CONFIANCA:
                self._log(f"  → candidata: {ref.referencia_formatada()} "
                          f"(confiança={ref.confianca:.0%})")
                self.gerenciador_janela.enfileirar(ref)
            else:
                self._log(f"  (descartado, confiança baixa: "
                          f"{ref.referencia_formatada()} = {ref.confianca:.0%})")

    # ---------------------- CONFIRMAÇÃO / HOLYRICS ----------------------

    def _ao_confirmar(self, ref):
        self._log(f"CONFIRMADO: {ref.referencia_formatada()}")

        def alvo():
            try:
                self.cliente_holyrics.exibir_por_referencia_detectada(ref)
                self._log(f"  ✔ exibido no Holyrics: {ref.referencia_formatada()}")
                self.contador_confirmados += 1
                self.root.after(0, lambda: self.rotulo_rodape.config(
                    text=f"Versículos exibidos nesta sessão: {self.contador_confirmados}"))
            except HolyricsAPIError as e:
                self._log(f"  ✘ falha ao exibir: {e}")

        threading.Thread(target=alvo, daemon=True).start()

    def _ao_cancelar(self, ref):
        self._log(f"Cancelado/expirado: {ref.referencia_formatada()}")

    # ---------------------- ENCERRAMENTO ----------------------

    def _ao_fechar(self):
        if self.evento_parar:
            self.evento_parar.set()
        self.root.destroy()

    def executar(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = SistemaVersiculos()
    app.executar()
