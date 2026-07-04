# -*- coding: utf-8 -*-
"""
Janela gráfica (popup) de confirmação de versículo detectado.

REGRA DE OURO: esta janela nunca chama o Holyrics sozinha. Ela só
recebe uma ReferenciaDetectada, mostra pro operador, e devolve a decisão
(confirmado ou não) via callback. Quem decide o que fazer com a
confirmação é o código que integra isso com holyrics_client.py.

Características:
  - Sempre no topo (always-on-top), pra não ficar escondida atrás do
    Holyrics ou de outras janelas durante o culto
  - Fonte grande, alto contraste — precisa ser lida rapidamente com o
    "rabo do olho" enquanto o operador acompanha o culto
  - Atalhos de teclado: Enter/Espaço = confirmar, Esc = cancelar
    (mais rápido que mirar o mouse durante uma transmissão ao vivo)
  - Some sozinha depois de TIMEOUT_PADRAO_SEGUNDOS se ninguém responder
    (evita acúmulo de popups órfãos se o operador se distrair) — conta
    como CANCELADO, nunca como confirmado, i.e. o padrão seguro é não
    exibir nada se não houver resposta
  - Múltiplas candidatas detectadas em sequência são enfileiradas, uma
    janela por vez — nunca sobrepõe popups

Uso standalone (demo, sem depender de áudio/Holyrics):
    python janela_confirmacao.py
"""

import tkinter as tk
from dataclasses import dataclass

TIMEOUT_PADRAO_SEGUNDOS = 12


@dataclass
class ReferenciaSimulada:
    """Usado só no modo demo/teste deste arquivo, pra não depender de
    importar parser_referencias.py aqui."""
    livro: str
    capitulo: int
    versiculo_inicio: int = None
    versiculo_fim: int = None
    confianca: float = 0.9
    texto_original: str = ""

    def referencia_formatada(self):
        if self.versiculo_inicio is None:
            return f"{self.livro} {self.capitulo}"
        if self.versiculo_fim and self.versiculo_fim != self.versiculo_inicio:
            return f"{self.livro} {self.capitulo}:{self.versiculo_inicio}-{self.versiculo_fim}"
        return f"{self.livro} {self.capitulo}:{self.versiculo_inicio}"


class JanelaConfirmacao:
    """
    Gerencia uma fila de candidatas e mostra uma janela de confirmação
    por vez. Pensada pra ser criada UMA vez no início do programa e
    reutilizada — não crie uma instância nova por candidata.

    Integração típica com o pipeline de áudio (que roda em thread
    separada): a thread de reconhecimento chama `.enfileirar(ref)`,
    que é thread-safe; a janela em si só é criada/mostrada na thread
    principal (tkinter exige isso).
    """

    def __init__(self, root, ao_confirmar, ao_cancelar=None,
                 timeout_segundos=TIMEOUT_PADRAO_SEGUNDOS):
        """
        root: instância de tk.Tk() já criada na thread principal
        ao_confirmar: função(ref) chamada quando o operador confirma
        ao_cancelar: função(ref) chamada quando o operador cancela ou
            deixa o tempo esgotar (opcional)
        timeout_segundos: tempo até a janela fechar sozinha como
            "cancelado" se ninguém responder
        """
        self.root = root
        self.ao_confirmar = ao_confirmar
        self.ao_cancelar = ao_cancelar
        self.timeout_segundos = timeout_segundos
        self._fila = []
        self._janela_ativa = None

    def enfileirar(self, ref):
        """Adiciona uma candidata à fila. Thread-safe (usa root.after
        pra sempre executar a criação de UI na thread principal)."""
        self.root.after(0, self._enfileirar_na_thread_principal, ref)

    def _enfileirar_na_thread_principal(self, ref):
        self._fila.append(ref)
        if self._janela_ativa is None:
            self._mostrar_proxima()

    def _mostrar_proxima(self):
        if not self._fila:
            self._janela_ativa = None
            return

        ref = self._fila.pop(0)
        self._janela_ativa = self._construir_janela(ref)

    def _construir_janela(self, ref):
        janela = tk.Toplevel(self.root)
        janela.title("Confirmar exibição")
        janela.attributes("-topmost", True)
        janela.resizable(False, False)
        janela.configure(bg="#1a1a2e")

        # centraliza na tela
        largura, altura = 520, 300
        tela_w = janela.winfo_screenwidth()
        tela_h = janela.winfo_screenheight()
        x = (tela_w - largura) // 2
        y = (tela_h - altura) // 2
        janela.geometry(f"{largura}x{altura}+{x}+{y}")

        tk.Label(
            janela, text="VERSÍCULO DETECTADO", font=("Segoe UI", 13, "bold"),
            fg="#8888aa", bg="#1a1a2e",
        ).pack(pady=(20, 5))

        tk.Label(
            janela, text=ref.referencia_formatada(),
            font=("Segoe UI", 28, "bold"), fg="#ffffff", bg="#1a1a2e",
        ).pack(pady=(0, 10))

        tk.Label(
            janela, text=f"confiança: {ref.confianca:.0%}",
            font=("Segoe UI", 11), fg="#66aa66" if ref.confianca >= 0.8 else "#ccaa44",
            bg="#1a1a2e",
        ).pack()

        if ref.texto_original:
            tk.Label(
                janela, text=f'"{ref.texto_original}"',
                font=("Segoe UI", 9, "italic"), fg="#666688", bg="#1a1a2e",
                wraplength=460,
            ).pack(pady=(8, 0))

        frame_botoes = tk.Frame(janela, bg="#1a1a2e")
        frame_botoes.pack(pady=(25, 10))

        btn_confirmar = tk.Button(
            frame_botoes, text="✔ EXIBIR (Enter)", font=("Segoe UI", 13, "bold"),
            bg="#2d7d46", fg="white", activebackground="#3a9d5a",
            width=16, height=2, relief="flat", cursor="hand2",
            command=lambda: self._resolver(janela, ref, confirmado=True),
        )
        btn_confirmar.pack(side="left", padx=10)

        btn_cancelar = tk.Button(
            frame_botoes, text="✘ Cancelar (Esc)", font=("Segoe UI", 11),
            bg="#3a3a4a", fg="white", activebackground="#4a4a5a",
            width=14, height=2, relief="flat", cursor="hand2",
            command=lambda: self._resolver(janela, ref, confirmado=False),
        )
        btn_cancelar.pack(side="left", padx=10)

        rotulo_timeout = tk.Label(
            janela, text="", font=("Segoe UI", 9), fg="#555577", bg="#1a1a2e",
        )
        rotulo_timeout.pack(pady=(5, 0))

        janela.bind(
            "<Return>", lambda e: self._resolver(janela, ref, confirmado=True)
        )
        janela.bind(
            "<KP_Enter>", lambda e: self._resolver(janela, ref, confirmado=True)
        )
        janela.bind(
            "<Escape>", lambda e: self._resolver(janela, ref, confirmado=False)
        )
        janela.protocol(
            "WM_DELETE_WINDOW",
            lambda: self._resolver(janela, ref, confirmado=False),
        )

        btn_confirmar.focus_set()

        # Garante que a janela realmente receba o foco do teclado do SO
        # (no Windows, popups criados via Toplevel às vezes não recebem
        # foco automático — sem isso, Enter/Esc não fazem nada até o
        # usuário clicar manualmente na janela primeiro).
        janela.lift()
        janela.focus_force()
        janela.after(50, btn_confirmar.focus_set)

        self._agendar_contagem_regressiva(janela, ref, rotulo_timeout,
                                           self.timeout_segundos)

        return janela

    def _agendar_contagem_regressiva(self, janela, ref, rotulo, segundos_restantes):
        if not janela.winfo_exists():
            return
        if segundos_restantes <= 0:
            self._resolver(janela, ref, confirmado=False)
            return
        rotulo.config(text=f"fecha automaticamente em {segundos_restantes}s "
                            f"(sem confirmação = não exibe)")
        janela.after(
            1000, self._agendar_contagem_regressiva, janela, ref, rotulo,
            segundos_restantes - 1,
        )

    def _resolver(self, janela, ref, confirmado):
        janela.destroy()
        if confirmado:
            self.ao_confirmar(ref)
        elif self.ao_cancelar:
            self.ao_cancelar(ref)
        self._mostrar_proxima()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()  # não mostramos uma janela principal, só os popups

    def confirmado(ref):
        print(f"[CONFIRMADO] {ref.referencia_formatada()} -> enviaria pro Holyrics agora")

    def cancelado(ref):
        print(f"[CANCELADO] {ref.referencia_formatada()}")

    gerenciador = JanelaConfirmacao(root, ao_confirmar=confirmado, ao_cancelar=cancelado)

    # demo: enfileira 3 candidatas de teste, uma vai aparecer depois da outra
    gerenciador.enfileirar(ReferenciaSimulada(
        livro="João", capitulo=3, versiculo_inicio=16, confianca=0.9,
        texto_original="João três dezesseis",
    ))
    gerenciador.enfileirar(ReferenciaSimulada(
        livro="Salmos", capitulo=23, confianca=0.55,
        texto_original="Salmo vinte e três",
    ))
    gerenciador.enfileirar(ReferenciaSimulada(
        livro="1 Coríntios", capitulo=13, versiculo_inicio=4, versiculo_fim=7,
        confianca=0.95, texto_original="primeira de coríntios treze quatro a sete",
    ))

    root.mainloop()
