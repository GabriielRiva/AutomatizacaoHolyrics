# Sistema de Versículos

Sistema que escuta o áudio do culto (via interface USB ligada na saída
Aux/Matrix de uma mesa X32), transcreve a fala em português com
reconhecimento de voz offline (Vosk), detecta referências bíblicas
citadas ("João três dezesseis", "Salmo cento e dezenove versículo
cento e cinco"...) e, **depois de confirmação manual do operador**,
exibe o versículo automaticamente no Holyrics.

**Regra de ouro do projeto:** nada é exibido no telão sem confirmação
explícita de uma pessoa. O sistema só sugere candidatas.

## Como funciona (visão geral)

```
áudio (X32 -> USB) -> captura_audio.py -> Vosk (STT) -> parser_referencias.py
   -> janela_confirmacao.py (popup) -> [operador confirma] -> holyrics_client.py -> Holyrics
```

## Arquivos

| Arquivo | Função |
|---|---|
| `sistema_completo.py` | **Programa principal.** Painel de controle gráfico (Tkinter) com botão iniciar/parar captura, log de atividade e popups de confirmação. |
| `captura_audio.py` | Protótipo de captura de áudio + STT rodando direto no terminal (sem GUI), útil pra testar o pipeline de reconhecimento isoladamente. |
| `confirmar_e_exibir.py` | Protótipo da camada de confirmação em modo texto/console (sem GUI), pra testar parser + Holyrics sem tkinter. |
| `janela_confirmacao.py` | Popup de confirmação (Tkinter) — mostra a referência detectada e espera Enter (confirmar) / Esc (cancelar) / timeout. |
| `holyrics_client.py` | Cliente da API HTTP do Holyrics (autenticação por token, ação `ShowVerse`, etc.) |
| `parser_referencias.py` | Núcleo: interpreta texto transcrito e extrai referências bíblicas (livro, capítulo, versículo). |
| `numeros_pt.py` | Converte números por extenso em português ("vinte e três" → 23). |
| `biblia_livros.py` | Dicionário dos 66 livros da Bíblia com todas as variações faladas (abreviações, "primeiro/segundo", etc.) e a numeração canônica usada nos IDs do Holyrics. |
| `listar_dispositivos.py` | Lista os dispositivos de áudio disponíveis no sistema, pra você achar o índice da interface USB da X32. |
| `testar_arquivo_audio.py` | Testa o pipeline STT + parser usando um arquivo `.wav` gravado, sem precisar de microfone ao vivo. |

## Instalação

Requer **Python 3.9+**.

```bash
git clone <url-do-seu-repositorio>
cd sistema-versiculos
pip install -r requirements.txt
```

No Linux, o Tkinter às vezes precisa ser instalado à parte:
```bash
sudo apt install python3-tk
```

### Baixe o modelo de voz Vosk (português)

1. Baixe em: https://alphacephei.com/vosk/models
   - Recomendado pra começar: `vosk-model-small-pt-0.3` (~50 MB, rápido)
   - Pra mais precisão depois: `vosk-model-pt-fb-v0.1.1-20220516_2113`
2. Descompacte a pasta baixada e renomeie (ou ajuste o caminho) pra
   `modelo_vosk_pt/` na raiz do projeto.

Essa pasta **não deve ir pro git** (já está no `.gitignore` — é grande
e é só um download, não código).

### Configure o Holyrics

1. No Holyrics: **Arquivo > Configurações > API Server**
2. Marque **"API Server - Local"**
3. **Gerenciar Permissões > Adicionar**, dê um nome ao token (ex:
   `sistema-versiculos`)
4. Habilite a permissão **ShowVerse** (e `GetBibleVersions` se quiser)
5. Copie o token gerado

**Nunca coloque o token direto no código.** Configure como variável de
ambiente antes de rodar:

```bash
# Linux/Mac
export HOLYRICS_TOKEN="seu_token_aqui"

# Windows (PowerShell)
$env:HOLYRICS_TOKEN = "seu_token_aqui"
```

## Uso

1. Descubra o índice da sua interface de áudio:
   ```bash
   python listar_dispositivos.py
   ```
   Anote o número `[i]` da interface ligada no Aux/Matrix da X32 e
   ajuste `DEVICE_INDEX` em `sistema_completo.py`.

2. Rode o programa principal:
   ```bash
   python sistema_completo.py
   ```
   - Espere o modelo carregar (o botão "Iniciar Captura" habilita
     sozinho).
   - Clique em "Iniciar Captura" quando o culto começar.
   - Quando uma referência bíblica for detectada na fala, um popup
     aparece pra você confirmar (Enter) ou cancelar (Esc). Sem
     resposta em 12s, cancela automaticamente — nunca exibe sozinho.

### Testar sem culto ao vivo

- Testar só o parser de texto (sem áudio):
  ```bash
  python parser_referencias.py
  ```
- Testar com um áudio já gravado:
  ```bash
  python testar_arquivo_audio.py caminho/do/audio.wav
  ```
- Testar a camada de confirmação em modo texto:
  ```bash
  python confirmar_e_exibir.py
  ```

## Status / limitações conhecidas

- O ID numérico dos livros usado em `holyrics_client.py` (formato
  `BBCCCVVV`) segue a numeração canônica padrão (Gênesis=1 ...
  Apocalipse=66). **Teste no seu Holyrics antes do culto de verdade**
  pra confirmar que bate com a instalação — se der erro "Item not
  found", o sistema cai automaticamente pro método por texto
  (`exibir_versiculo`), que depende do nome do livro bater com a
  versão da bíblia instalada.
- Referências só de capítulo (ex: "Salmo 23" inteiro, sem versículo)
  usam sempre o método por texto, não o ID numérico.
- Ainda não há testes automatizados (`pytest`) — as validações até
  agora foram manuais, rodando `parser_referencias.py` diretamente.

## Licença

Defina a licença que preferir (ex: MIT) antes de tornar o repositório
público.
