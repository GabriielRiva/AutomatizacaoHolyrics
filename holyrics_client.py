# -*- coding: utf-8 -*-
"""
Cliente para a API HTTP do Holyrics (https://github.com/holyrics/API-Server).

Implementa o método de autenticação por TOKEN direto (simples), adequado
pro nosso caso de uso: o programa Holyrics roda no mesmo computador (ou
mesma rede local confiável) que este script, sem exposição à internet.

CONFIGURAÇÃO NO HOLYRICS (antes de usar):
  1. Menu Arquivo > Configurações > API Server
  2. Marque a caixa "API Server - Local"
  3. Clique em "Gerenciar Permissões" > "Adicionar"
  4. Dê um nome pro token (ex: "sistema-versiculos") e clique OK
  5. Clique em "Editar" no token criado e habilite, na coluna "Local",
     a permissão da ação ShowVerse (e GetBibleVersions se quiser listar
     versões disponíveis)
  6. Copie o token gerado — ele vai na variável TOKEN abaixo (ou em
     variável de ambiente, ver comentário no final do arquivo)
  7. Anote a porta configurada (padrão: 8091)

Uso básico:
    from holyrics_client import HolyricsClient

    cliente = HolyricsClient(token="SEU_TOKEN_AQUI")
    cliente.exibir_versiculo("João 3:16")
"""

import json
import requests


class HolyricsAPIError(Exception):
    """Erro retornado pela API do Holyrics (ex: token inválido, sem
    permissão, ação desconhecida)."""
    pass


class HolyricsClient:
    def __init__(self, token, ip="127.0.0.1", port=8091, timeout=5,
                 versao_padrao="pt_nvi"):
        """
        token: token de acesso criado nas configurações do API Server
        ip: IP do computador rodando o Holyrics (127.0.0.1 se for o
            mesmo PC deste script, que é o caso normal — o PC das
            mídias roda tanto o Holyrics quanto este sistema)
        port: porta configurada no API Server (padrão 8091)
        timeout: tempo máximo (segundos) de espera pela resposta —
            importante ficar baixo, pra não travar o pipeline ao vivo
            se o Holyrics estiver com problema
        versao_padrao: chave da versão da bíblia a usar quando nenhuma
            for especificada explicitamente (ex: "pt_nvi", "pt_arc",
            "pt_naa"). O Holyrics pode não ter uma versão padrão
            configurada na instalação, o que causa erro "Item not
            found" em ShowVerse se a versão não for informada.
        """
        self.token = token
        self.base_url = f"http://{ip}:{port}/api"
        self.timeout = timeout
        self.versao_padrao = versao_padrao

    def _chamar(self, action, payload=None):
        url = f"{self.base_url}/{action}"
        params = {"token": self.token}
        body = payload or {}

        try:
            resp = requests.post(
                url, params=params, json=body, timeout=self.timeout
            )
        except requests.exceptions.ConnectionError as e:
            raise HolyricsAPIError(
                f"Não foi possível conectar ao Holyrics em {url}. "
                f"Confirme que o programa está aberto e o API Server "
                f"está ativado. Detalhe: {e}"
            )
        except requests.exceptions.Timeout:
            raise HolyricsAPIError(
                f"Holyrics não respondeu em {self.timeout}s (ação: {action})."
            )

        try:
            dados = resp.json()
        except json.JSONDecodeError:
            raise HolyricsAPIError(
                f"Resposta inesperada do Holyrics (não é JSON): {resp.text[:200]}"
            )

        if dados.get("status") != "ok":
            raise HolyricsAPIError(
                f"Holyrics retornou erro na ação '{action}': {dados}"
            )

        return dados.get("data")

    def testar_conexao(self):
        """Faz uma chamada leve só pra confirmar que o token e a conexão
        estão funcionando. Levanta HolyricsAPIError se algo estiver
        errado. Retorna True se tudo OK."""
        self._chamar("GetBibleVersions")
        return True

    def checar_permissoes(self, acoes):
        """
        Verifica se o token atual tem permissão pra executar as ações
        listadas (ex: ["ShowVerse", "GetBibleVersions"]). Útil pra
        diagnosticar erros que podem ser confundidos com "referência
        não encontrada" quando na verdade é falta de permissão.
        Retorna o dicionário de dados cru devolvido pelo Holyrics.
        """
        return self._chamar("CheckToken", {"actions": acoes})

    def info_apresentacao_atual(self):
        """Chamada simples de diagnóstico — só pega o estado atual do
        Holyrics, não exibe nada. Útil pra confirmar que ações básicas
        funcionam com o token, isolando problemas específicos de
        ShowVerse."""
        return self._chamar("GetCPInfo")

    def exibir_versiculo(self, referencia, versao=None, quick_presentation=False):
        """
        Exibe um versículo (ou intervalo) no telão via ShowVerse, usando
        o texto da referência (ex: "João 3:16"). ATENÇÃO: isso depende
        do Holyrics conseguir casar o nome do livro em português com a
        versão da bíblia instalada — se der erro "Item not found",
        prefira usar exibir_por_referencia_detectada(), que usa ID
        numérico e não depende de nomenclatura.

        referencia: string no formato "Livro cap:vers" ou
            "Livro cap:vers-vers_fim"
        versao: abreviação da versão da bíblia a usar (ex: "ARC", "NVI").
            Se None, usa a versão padrão configurada no Holyrics.
        quick_presentation: se True, mostra em popup sem interromper a
            apresentação atual
        """
        payload = {
            "references": referencia,
            "version": versao or self.versao_padrao,
        }
        if quick_presentation:
            payload["quick_presentation"] = True

        return self._chamar("ShowVerse", payload)

    def exibir_por_referencia_detectada(self, ref, versao=None, quick_presentation=False):
        """
        Exibe um versículo usando o ID numérico canônico (formato
        BBCCCVVV do Holyrics), calculado a partir de um objeto
        ReferenciaDetectada do parser_referencias.py. Isso é mais
        confiável que exibir_versiculo() porque não depende de como a
        versão da bíblia instalada nomeia os livros em português —
        evita erros tipo "Item not found" por divergência de nome.

        Requer que ref.livro exista em biblia_livros.NUMERO_LIVRO.
        Não funciona pra referências sem versículo (só capítulo, ex:
        "Salmo 23" inteiro) — nesse caso cai automaticamente pro
        método de texto (exibir_versiculo), que pode ou não funcionar
        dependendo da versão instalada.
        """
        from biblia_livros import NUMERO_LIVRO

        if ref.versiculo_inicio is None:
            # sem versículo específico (referência de capítulo inteiro):
            # não dá pra montar ID de versículo único, cai pro texto
            return self.exibir_versiculo(
                ref.referencia_formatada(), versao=versao,
                quick_presentation=quick_presentation,
            )

        numero_livro = NUMERO_LIVRO.get(ref.livro)
        if numero_livro is None:
            raise HolyricsAPIError(
                f"Livro '{ref.livro}' não está no mapeamento NUMERO_LIVRO."
            )

        def calcular_id(capitulo, versiculo):
            return f"{numero_livro:02d}{capitulo:03d}{versiculo:03d}"

        v_fim = ref.versiculo_fim or ref.versiculo_inicio

        if v_fim == ref.versiculo_inicio:
            payload = {"id": calcular_id(ref.capitulo, ref.versiculo_inicio)}
        else:
            ids = [
                calcular_id(ref.capitulo, v)
                for v in range(ref.versiculo_inicio, v_fim + 1)
            ]
            payload = {"ids": ids}

        payload["version"] = versao or self.versao_padrao
        if quick_presentation:
            payload["quick_presentation"] = True

        return self._chamar("ShowVerse", payload)

    def fechar_apresentacao_atual(self):
        """Encerra a apresentação atual (equivalente a apertar ESC no
        Holyrics), voltando pro estado ocioso."""
        return self._chamar("CloseCurrentPresentation")

    def listar_versoes_biblia(self):
        """Retorna a lista de versões da bíblia instaladas no Holyrics."""
        return self._chamar("GetBibleVersions")


if __name__ == "__main__":
    # Teste manual rápido. Ajuste TOKEN antes de rodar.
    # Nunca deixe o token real commitado em repositório público — prefira
    # ler de variável de ambiente em produção:
    #   import os; TOKEN = os.environ["HOLYRICS_TOKEN"]
    TOKEN = "COLOQUE_SEU_TOKEN_AQUI"

    cliente = HolyricsClient(token=TOKEN)

    print("Testando conexão com o Holyrics...")
    try:
        cliente.testar_conexao()
        print("Conexão OK!")
    except HolyricsAPIError as e:
        print(f"Falha na conexão: {e}")
        raise SystemExit(1)

    referencia_teste = "João 3:16"
    print(f"Exibindo '{referencia_teste}'...")
    try:
        cliente.exibir_versiculo(referencia_teste)
        print("Enviado com sucesso. Confira o telão/preview do Holyrics.")
    except HolyricsAPIError as e:
        print(f"Falha ao exibir: {e}")
