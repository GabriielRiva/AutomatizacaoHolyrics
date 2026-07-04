# Script de build + publicação do Sistema de Versículos.
#
# Resolve o problema de token/modelo/corpus sumirem a cada rebuild: o
# PyInstaller sempre limpa a pasta dist\SistemaVersiculos do zero, mas
# a pasta de INSTALAÇÃO (definida abaixo) nunca é tocada por ele -- só
# copiamos pra lá o que realmente mudou (o .exe e o _internal).
#
# Uso:
#   .\publicar.ps1
#
# Rode sempre da raiz do projeto (onde está o sistema_completo.py).

$ErrorActionPreference = "Stop"

# Pasta onde o programa "de verdade" vai morar -- ajuste se quiser.
$PastaInstalacao = "C:\Projetos\sistema-versiculos\Instalado"

Write-Host "== 1) Buildando com PyInstaller ==" -ForegroundColor Cyan
pyinstaller --onedir --windowed --noconfirm --name SistemaVersiculos --collect-all vosk --collect-all sounddevice sistema_completo.py

if (-not (Test-Path "dist\SistemaVersiculos\SistemaVersiculos.exe")) {
    Write-Host "ERRO: build não gerou o .exe esperado. Veja os erros acima." -ForegroundColor Red
    exit 1
}

Write-Host "== 2) Preparando pasta de instalação ==" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $PastaInstalacao | Out-Null

Write-Host "== 3) Copiando .exe e _internal (sempre sobrescreve) ==" -ForegroundColor Cyan
Copy-Item "dist\SistemaVersiculos\SistemaVersiculos.exe" -Destination $PastaInstalacao -Force
Copy-Item "dist\SistemaVersiculos\_internal" -Destination $PastaInstalacao -Recurse -Force

Write-Host "== 4) Copiando modelo/corpus SE ainda não existirem na instalação ==" -ForegroundColor Cyan
if (-not (Test-Path "$PastaInstalacao\modelo_vosk_pt")) {
    if (Test-Path "modelo_vosk_pt") {
        Write-Host "  Copiando modelo_vosk_pt (pode demorar, é grande)..."
        Copy-Item "modelo_vosk_pt" -Destination $PastaInstalacao -Recurse -Force
    } else {
        Write-Host "  AVISO: modelo_vosk_pt não encontrado na raiz do projeto. Copie manualmente." -ForegroundColor Yellow
    }
} else {
    Write-Host "  modelo_vosk_pt já existe na instalação, mantido como está."
}

if (-not (Test-Path "$PastaInstalacao\biblia_texto_dominio_publico.json")) {
    if (Test-Path "biblia_texto_dominio_publico.json") {
        Copy-Item "biblia_texto_dominio_publico.json" -Destination $PastaInstalacao -Force
        Write-Host "  biblia_texto_dominio_publico.json copiado."
    } else {
        Write-Host "  AVISO: biblia_texto_dominio_publico.json não encontrado na raiz do projeto." -ForegroundColor Yellow
    }
} else {
    Write-Host "  biblia_texto_dominio_publico.json já existe na instalação, mantido como está."
}

Write-Host ""
Write-Host "== Pronto! ==" -ForegroundColor Green
Write-Host "Programa instalado em: $PastaInstalacao"
Write-Host "O holyrics_token.txt (se existir) NÃO foi tocado -- ele só é criado/atualizado"
Write-Host "pela própria tela do programa (campo Token + botão Salvar), e fica salvo"
Write-Host "para sempre nessa pasta de instalação, mesmo que você rebuilde de novo."
Write-Host ""
Write-Host "Abra sempre o .exe a partir de: $PastaInstalacao\SistemaVersiculos.exe"
