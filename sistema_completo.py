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
from tkinter import scrolledtext, ttk
from datetime import datetime

import sounddevice as sd
from vosk import KaldiRecognizer, Model

from parser_referencias import parse_referencia, ReferenciaDetectada
from janela_confirmacao import JanelaConfirmacao
from holyrics_client import HolyricsClient, HolyricsAPIError
from busca_versiculo_texto import carregar_corpus, normalizar_texto


def obter_pasta_base():
    """
    Retorna a pasta onde o programa está rodando de fato.

    Quando rodado como script Python normal, é a pasta deste arquivo.
    Quando empacotado como .exe pelo PyInstaller, __file__ aponta pra
    dentro da pasta temporária de extração — o que queremos é a pasta
    onde o .exe foi colocado, pra achar 'modelo_vosk_pt' e o arquivo de
    token ao lado dele.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def carregar_token_holyrics():
    """
    Busca o token do Holyrics, nesta ordem de prioridade:
      1) variável de ambiente HOLYRICS_TOKEN (bom pra desenvolvimento)
      2) arquivo 'holyrics_token.txt' na mesma pasta do programa (bom
         pra quem só vai clicar duas vezes no .exe — sem terminal)

    O arquivo texto deve conter só o token, numa linha só, sem aspas.
    Nunca deve ir pro git (ver .gitignore).
    """
    token_env = os.environ.get("HOLYRICS_TOKEN")
    if token_env:
        return token_env

    caminho_arquivo = os.path.join(PASTA_BASE, "holyrics_token.txt")
    if os.path.isfile(caminho_arquivo):
        # utf-8-sig remove automaticamente o BOM que o Bloco de Notas
        # do Windows às vezes adiciona no início do arquivo — sem isso,
        # um caractere invisível ficava colado no início do token e o
        # Holyrics rejeitava como "invalid token" mesmo com o valor
        # certo digitado.
        with open(caminho_arquivo, "r", encoding="utf-8-sig") as f:
            token_arquivo = f.read().strip()
        if token_arquivo:
            return token_arquivo

    return "COLOQUE_SEU_TOKEN_AQUI"


PASTA_BASE = obter_pasta_base()

# ----------------------- CONFIGURAÇÃO -----------------------
# Token do Holyrics: veja carregar_token_holyrics() acima pra entender
# de onde ele vem (variável de ambiente OU arquivo holyrics_token.txt
# na mesma pasta do programa/.exe). NUNCA deixe o token real commitado
# no git — o arquivo holyrics_token.txt já está no .gitignore.
HOLYRICS_TOKEN = carregar_token_holyrics()
# Valor mostrado no campo da interface: vazio se ainda não há token
# configurado (evita mostrar o texto de placeholder como se fosse um
# token de verdade).
HOLYRICS_TOKEN_INICIAL = "" if HOLYRICS_TOKEN == "COLOQUE_SEU_TOKEN_AQUI" else HOLYRICS_TOKEN
HOLYRICS_IP = "127.0.0.1"
HOLYRICS_PORTA = 8091
HOLYRICS_VERSAO_BIBLIA = "pt_nvi"   # NVI — troque se sua igreja usar outra

MODEL_PATH = os.path.join(PASTA_BASE, "modelo_vosk_pt")
DEVICE_INDEX = None              # Valor inicial (None = padrão do sistema).
                                  # A seleção real de dispositivo agora é
                                  # feita pelo combobox na interface —
                                  # ver self.device_index_selecionado.
SAMPLE_RATE_VOSK = 16000
BLOCO_MS = 250

LIMIAR_CONFIANCA = 0.6
TIMEOUT_CONFIRMACAO_SEGUNDOS = 12

# Reconhecimento de versículo citado "de cor" (sem falar a referência),
# comparando a fala transcrita contra o texto da Bíblia (ver
# busca_versiculo_texto.py). Limiar mais alto que o de referência
# direta de propósito -- citação de memória nunca bate 100% com o
# texto escrito, então preferimos ser mais conservadores aqui.
CAMINHO_CORPUS_BIBLICO = os.path.join(PASTA_BASE, "biblia_texto_dominio_publico.json")
LIMIAR_CONFIANCA_TEXTO_LIVRE = 0.6
# --------------------------------------------------------------


class SistemaVersiculos:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema de Versículos — Painel de Controle")
        self.root.geometry("620x540")
        self.root.configure(bg="#1a1a2e")
        self.root.protocol("WM_DELETE_WINDOW", self._ao_fechar)

        self.modelo_vosk = None
        self.corpus_biblico = None
        self.versiculo_atual_exibido = None   # (livro, capitulo, vers_ini, vers_fim)
        self.thread_captura = None
        self.evento_parar = None
        self.capturando = False
        self.contador_confirmados = 0
        self.mapa_dispositivos = {}          # texto exibido -> índice do dispositivo
        self.device_index_selecionado = DEVICE_INDEX  # None = padrão do sistema

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
        self._atualizar_lista_dispositivos()
        self._logar_diagnostico_inicial()
        self._verificar_holyrics_em_thread()
        self._carregar_modelo_em_thread()

    def _logar_diagnostico_inicial(self):
        """Loga de onde vieram as configurações principais, sem expor o
        token completo — só o suficiente pra diagnosticar problema de
        leitura de arquivo/variável de ambiente no local do culto."""
        self._log(f"Pasta base do programa: {PASTA_BASE}")

        if os.environ.get("HOLYRICS_TOKEN"):
            origem_token = "variável de ambiente HOLYRICS_TOKEN"
        elif os.path.isfile(os.path.join(PASTA_BASE, "holyrics_token.txt")):
            origem_token = "arquivo holyrics_token.txt"
        else:
            origem_token = "NENHUMA FONTE ENCONTRADA (usando placeholder)"

        if HOLYRICS_TOKEN and HOLYRICS_TOKEN != "COLOQUE_SEU_TOKEN_AQUI":
            preview = f"{HOLYRICS_TOKEN[:4]}...{HOLYRICS_TOKEN[-2:]} ({len(HOLYRICS_TOKEN)} caracteres)"
        else:
            preview = "(nenhum token configurado)"

        self._log(f"Token do Holyrics: origem = {origem_token}, valor = {preview}")

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
        self.rotulo_holyrics.pack(pady=(0, 10))

        frame_token = tk.Frame(self.root, bg="#1a1a2e")
        frame_token.pack(pady=(0, 15), padx=20, fill="x")

        tk.Label(
            frame_token, text="Token do Holyrics:", font=("Segoe UI", 9, "bold"),
            fg="#8888aa", bg="#1a1a2e",
        ).pack(side="left", padx=(0, 8))

        self.var_token = tk.StringVar(value=HOLYRICS_TOKEN_INICIAL)
        self.entrada_token = tk.Entry(
            frame_token, textvariable=self.var_token, show="•",
            font=("Consolas", 10), bg="#0f0f1a", fg="#eeeeee",
            insertbackground="white", relief="flat", width=22,
        )
        self.entrada_token.pack(side="left", padx=(0, 8), ipady=4)

        self.var_mostrar_token = tk.BooleanVar(value=False)
        tk.Checkbutton(
            frame_token, text="mostrar", variable=self.var_mostrar_token,
            command=self._alternar_visibilidade_token,
            font=("Segoe UI", 8), fg="#8888aa", bg="#1a1a2e",
            selectcolor="#0f0f1a", activebackground="#1a1a2e",
            activeforeground="#8888aa",
        ).pack(side="left", padx=(0, 8))

        tk.Button(
            frame_token, text="Salvar", font=("Segoe UI", 9, "bold"),
            bg="#2d5d7d", fg="white", activebackground="#3a7a9d",
            relief="flat", cursor="hand2", padx=10,
            command=self._salvar_token,
        ).pack(side="left")

        frame_mic = tk.Frame(self.root, bg="#1a1a2e")
        frame_mic.pack(pady=(0, 15), padx=20, fill="x")

        tk.Label(
            frame_mic, text="Microfone / entrada de áudio:",
            font=("Segoe UI", 9, "bold"), fg="#8888aa", bg="#1a1a2e",
        ).pack(side="left", padx=(0, 8))

        estilo = ttk.Style()
        estilo.theme_use("default")
        estilo.configure(
            "Escuro.TCombobox", fieldbackground="#0f0f1a", background="#0f0f1a",
            foreground="#eeeeee", arrowcolor="#eeeeee",
        )

        self.var_dispositivo = tk.StringVar()
        self.combo_dispositivo = ttk.Combobox(
            frame_mic, textvariable=self.var_dispositivo, state="readonly",
            font=("Segoe UI", 9), width=32, style="Escuro.TCombobox",
        )
        self.combo_dispositivo.pack(side="left", padx=(0, 8))
        self.combo_dispositivo.bind(
            "<<ComboboxSelected>>", self._ao_selecionar_dispositivo
        )

        tk.Button(
            frame_mic, text="🔄 Atualizar lista", font=("Segoe UI", 9),
            bg="#3a3a4a", fg="white", activebackground="#4a4a5a",
            relief="flat", cursor="hand2", padx=8,
            command=self._atualizar_lista_dispositivos,
        ).pack(side="left")

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

    def _alternar_visibilidade_token(self):
        """Alterna entre mostrar o token em texto puro ou escondido
        atrás de •, conforme o checkbox 'mostrar'."""
        self.entrada_token.config(show="" if self.var_mostrar_token.get() else "•")

    def _salvar_token(self):
        """
        Salva o token digitado na interface em holyrics_token.txt (na
        pasta do programa) e aplica a mudança na hora, sem precisar
        reiniciar — atualiza o cliente Holyrics já em uso e testa a
        conexão de novo automaticamente.
        """
        novo_token = self.var_token.get().strip()
        if not novo_token:
            self._log("Token vazio — nada foi salvo.")
            return

        caminho_arquivo = os.path.join(PASTA_BASE, "holyrics_token.txt")
        try:
            with open(caminho_arquivo, "w", encoding="utf-8") as f:
                f.write(novo_token)
        except OSError as e:
            self._log(f"ERRO ao salvar o token em disco: {e}")
            return

        self.cliente_holyrics.definir_token(novo_token)
        self._log("Token salvo. Testando conexão com o Holyrics...")
        self._verificar_holyrics_em_thread()

    def _atualizar_lista_dispositivos(self):
        """
        Consulta os dispositivos de áudio de entrada disponíveis no
        sistema (via sounddevice) e popula o combobox. Chamado ao abrir
        o programa e sempre que o botão 'Atualizar lista' é clicado —
        útil se uma interface USB for conectada depois do programa já
        estar aberto.
        """
        try:
            dispositivos = sd.query_devices()
            indice_padrao = sd.default.device[0]
        except Exception as e:
            self._log(f"ERRO ao listar dispositivos de áudio: {e}")
            return

        self.mapa_dispositivos = {}
        opcoes = []
        indice_selecao_padrao = None

        for i, d in enumerate(dispositivos):
            if d["max_input_channels"] <= 0:
                continue
            marcador = " (padrão do sistema)" if i == indice_padrao else ""
            texto = f"[{i}] {d['name']}{marcador}"
            self.mapa_dispositivos[texto] = i
            opcoes.append(texto)
            if i == indice_padrao:
                indice_selecao_padrao = texto

        self.combo_dispositivo["values"] = opcoes

        if not opcoes:
            self._log("Nenhum dispositivo de entrada de áudio encontrado.")
            return

        # Mantém a seleção atual se ela ainda existir na lista nova;
        # senão, cai pro dispositivo padrão do sistema (ou o primeiro
        # da lista, se nem isso existir).
        selecao_atual = self.var_dispositivo.get()
        if selecao_atual in self.mapa_dispositivos:
            return

        escolhido = indice_selecao_padrao or opcoes[0]
        self.var_dispositivo.set(escolhido)
        self.device_index_selecionado = self.mapa_dispositivos[escolhido]

    def _ao_selecionar_dispositivo(self, event=None):
        texto = self.var_dispositivo.get()
        indice = self.mapa_dispositivos.get(texto)
        if indice is not None:
            self.device_index_selecionado = indice
            self._log(f"Dispositivo de áudio selecionado: {texto}")

    # ---------------------- HOLYRICS ----------------------

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
            except Exception as e:
                self.root.after(0, lambda: self.rotulo_status.config(
                    text="● Erro ao carregar modelo Vosk", fg="#cc6666"))
                self._log(f"ERRO ao carregar modelo Vosk: {e}")
                self._log(f"Confirme que a pasta '{MODEL_PATH}' contém o "
                          f"modelo descompactado.")
                return

            try:
                self.corpus_biblico = carregar_corpus(CAMINHO_CORPUS_BIBLICO)
                self._log(
                    f"Corpus bíblico carregado ({len(self.corpus_biblico.versiculos)} "
                    f"versículos) — reconhecimento por citação de cor habilitado."
                )
            except Exception as e:
                self.corpus_biblico = None
                self._log(f"AVISO: corpus bíblico não carregado ({e}). "
                          f"Reconhecimento por citação de cor ficará desabilitado, "
                          f"mas a detecção por referência direta ('livro capítulo "
                          f"versículo') continua funcionando normalmente.")

            self.root.after(0, self._modelo_pronto)

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
        self.combo_dispositivo.config(state="disabled")
        self._log("Captura iniciada.")

    def _parar_captura(self):
        if self.evento_parar:
            self.evento_parar.set()
        self.capturando = False
        self.botao_iniciar.config(text="▶ Iniciar Captura", bg="#2d7d46",
                                   activebackground="#3a9d5a")
        self.rotulo_status.config(text="● Pronto (parado)", fg="#8888aa")
        self.combo_dispositivo.config(state="readonly")
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
            device_info = sd.query_devices(self.device_index_selecionado, "input")
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
                device=self.device_index_selecionado, dtype="int16", channels=1,
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
            sd.check_input_settings(
                device=self.device_index_selecionado, samplerate=taxa_desejada,
                channels=1,
            )
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
                self._tratar_candidata(ref, origem="referência direta")
            else:
                self._log(f"  (descartado, confiança baixa: "
                          f"{ref.referencia_formatada()} = {ref.confianca:.0%})")

        # Só tenta reconhecer por citação de cor quando NÃO veio nenhuma
        # referência direta na frase — evita disparar as duas detecções
        # pra cima do mesmo trecho de fala.
        if not referencias and self.corpus_biblico is not None:
            texto_normalizado = normalizar_texto(texto)
            resultado = self.corpus_biblico.buscar(
                texto_normalizado, limiar_confianca=LIMIAR_CONFIANCA_TEXTO_LIVRE
            )
            if resultado:
                ref = ReferenciaDetectada(
                    livro=resultado.livro,
                    capitulo=resultado.capitulo,
                    versiculo_inicio=resultado.versiculo,
                    versiculo_fim=None,
                    confianca=resultado.confianca,
                    texto_original=texto,
                    trecho_casado="(reconhecido por citação de cor)",
                )
                self._tratar_candidata(ref, origem="citação de cor")

    def _tratar_candidata(self, ref, origem):
        """
        Ponto único de entrada pra qualquer candidata detectada, venha
        ela de referência direta ("João três dezesseis") ou de citação
        de cor (texto batendo com o corpus bíblico). Evita reabrir
        confirmação pra um versículo que já está sendo exibido no
        momento no Holyrics.
        """
        chave = (ref.livro, ref.capitulo, ref.versiculo_inicio, ref.versiculo_fim)
        if chave == self.versiculo_atual_exibido:
            self._log(f"  (já está sendo exibido, ignorando: {ref.referencia_formatada()})")
            return

        self._log(f"  → candidata ({origem}): {ref.referencia_formatada()} "
                  f"(confiança={ref.confianca:.0%})")
        self.gerenciador_janela.enfileirar(ref)

    # ---------------------- CONFIRMAÇÃO / HOLYRICS ----------------------

    def _ao_confirmar(self, ref):
        self._log(f"CONFIRMADO: {ref.referencia_formatada()}")

        def alvo():
            try:
                self.cliente_holyrics.exibir_por_referencia_detectada(ref)
                self._log(f"  ✔ exibido no Holyrics: {ref.referencia_formatada()}")
                self.versiculo_atual_exibido = (
                    ref.livro, ref.capitulo, ref.versiculo_inicio, ref.versiculo_fim
                )
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
