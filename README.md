# py-tana - your manga shelf extender

Uma ferramenta completa de linha de comando (CLI) para baixar, aprimorar via Inteligência Artificial e empacotar mangás diretamente do MangaDex. O projeto foi desenhado para criar uma "linha de montagem" automatizada, priorizando estabilidade, ordenação perfeita de capítulos e otimização de espaço em disco.

## Funcionalidades Principais

- **Menu CLI Interativo:** Escolha facilmente entre apenas baixar, empacotar ou aplicar aprimoramento de imagem.
- **Integração MangaDex API v5:** Download de imagens em alta qualidade direto dos servidores (MangaDex@Home), agrupados por volumes ou blocos de capítulos.
- **Upscaling com IA (Waifu2x):** Melhora a resolução e remove artefatos de compressão (JPEG noise) de retículas de mangá utilizando processamento via GPU (Vulkan).
- **Exportação Modular:** Gera arquivos `.cbz` (padrão ouro para leitores) e `.pdf` (suporte a páginas de orientação mista).
- **Ordenação Natural:** Utiliza ordenação natural (ex: Capítulo 2 antes do Capítulo 10) garantindo que a leitura flua corretamente.
- **Gestão de Disco:** Exclui automaticamente as pastas de imagens soltas (originais e aprimoradas) após a geração dos pacotes finais.

## Pré-requisitos

- Python 3.10+
- Drivers Vulkan instalados no sistema operacional.
- Binário do `waifu2x-ncnn-vulkan` configurado no PATH do sistema.

## Instalação (Fedora / Linux)

### 1. Preparando o ambiente Python
Recomenda-se o uso de um ambiente virtual para evitar conflitos de dependências no sistema operacional:

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

*(Certifique-se de que pacotes como `requests`, `natsort` e `Pillow`/`img2pdf` estejam no seu requirements.txt)*

### 2. Instalando o motor de Inteligência Artificial (Waifu2x)
O script utiliza a implementação em C++ do Waifu2x via API nativa do sistema operacional para evitar sobrecarga no interpretador Python.

Instale o loader do Vulkan:
    sudo dnf install vulkan-loader

Baixe e configure o binário oficial para execução global:
    wget https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-ubuntu.zip
    unzip waifu2x-ncnn-vulkan-20220728-ubuntu.zip
    sudo chmod +x waifu2x-ncnn-vulkan-20220728-ubuntu/waifu2x-ncnn-vulkan
    sudo mv waifu2x-ncnn-vulkan-20220728-ubuntu /opt/waifu2x
    sudo ln -s /opt/waifu2x/waifu2x-ncnn-vulkan /usr/local/bin/waifu2x-ncnn-vulkan

## Como Usar

Com o ambiente virtual ativado, inicie a aplicação principal:

    python main.py

O menu interativo será exibido:
1. **Baixar Imagens:** Apenas faz o download e mantém as imagens organizadas em pastas.
2. **Baixar e exportar (PDF/CBZ):** Baixa as imagens e imediatamente as empacota no formato escolhido, apagando as imagens soltas em seguida.
3. **Baixar, aprimorar as imagens e exportar (PDF/CBZ):** Fluxo completo. O sistema processará um volume por vez (Download -> Upscale via GPU -> CBZ/PDF -> Limpeza), impedindo travamentos por excesso de processos paralelos.

Para iniciar um download, o sistema solicitará o UUID do mangá desejado (encontrado na URL da obra no site do MangaDex).

## Arquitetura do Sistema

O projeto adota o princípio de separação de responsabilidades (Separation of Concerns). O processamento pesado de Deep Learning foi isolado do código de extração web. O `main.py` atua como orquestrador, utilizando a biblioteca `subprocess` para despachar diretórios inteiros para o motor autônomo do Waifu2x. Em caso de falha na IA (ex: falta de VRAM), o sistema executa um fallback seguro, empacotando os arquivos originais baixados sem interromper a esteira de produção.

_______________________________________

# py-tana - your manga shelf extender

A complete Command Line Interface (CLI) tool to download, AI-enhance, and package manga directly from MangaDex. The project is designed as an automated "assembly line", prioritizing stability, perfect chapter sorting, and disk space optimization.

## Key Features

- **Interactive CLI Menu:** Easily choose whether to just download, package, or apply image enhancement.
- **MangaDex API v5 Integration:** High-quality image downloads directly from their servers (MangaDex@Home), grouped by volumes or chapter batches.
- **AI Upscaling (Waifu2x):** Improves resolution and removes compression artifacts (JPEG noise) from manga screentones using GPU processing (Vulkan).
- **Modular Export:** Generates `.cbz` (gold standard for comic readers) and `.pdf` files (supporting mixed-orientation pages).
- **Natural Sorting:** Implements natural sorting (e.g., Chapter 2 comes before Chapter 10), ensuring a flawless reading flow.
- **Disk Management:** Automatically deletes raw and enhanced image folders once the final packages are generated.

## Prerequisites

- Python 3.10+
- Vulkan drivers installed on the operating system.
- `waifu2x-ncnn-vulkan` binary configured in the system PATH.

## Installation (Fedora / Linux)

### 1. Setting up the Python environment
It is recommended to use a virtual environment to avoid OS dependency conflicts:

    python -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt

*(Ensure packages like `requests`, `natsort`, and `Pillow`/`img2pdf` are in your requirements.txt)*

### 2. Installing the AI engine (Waifu2x)
The script uses the C++ implementation of Waifu2x via the native OS API to prevent Python interpreter overhead.

Install the Vulkan loader:
    sudo dnf install vulkan-loader

Download and configure the official binary for global execution:
    wget https://github.com/nihui/waifu2x-ncnn-vulkan/releases/download/20220728/waifu2x-ncnn-vulkan-20220728-ubuntu.zip
    unzip waifu2x-ncnn-vulkan-20220728-ubuntu.zip
    sudo chmod +x waifu2x-ncnn-vulkan-20220728-ubuntu/waifu2x-ncnn-vulkan
    sudo mv waifu2x-ncnn-vulkan-20220728-ubuntu /opt/waifu2x
    sudo ln -s /opt/waifu2x/waifu2x-ncnn-vulkan /usr/local/bin/waifu2x-ncnn-vulkan

## How to Use

With the virtual environment activated, start the main application:

    python main.py

The interactive menu will be displayed:
1. **Download Images:** Only downloads and keeps the images organized in folders.
2. **Download and export (PDF/CBZ):** Downloads the images and immediately packages them in the chosen format, deleting the loose images afterward.
3. **Download, enhance images, and export (PDF/CBZ):** Complete workflow. The system processes one volume at a time (Download -> GPU Upscale -> CBZ/PDF -> Cleanup), preventing crashes caused by excessive parallel processes.

To start a download, the system will prompt for the target manga's UUID (found in the manga's URL on the MangaDex website).

## System Architecture

The project adopts the Separation of Concerns principle. Heavy Deep Learning processing has been isolated from the web scraping code. The `main.py` acts as an orchestrator, using the `subprocess` library to dispatch entire directories to the autonomous Waifu2x engine. If the AI fails (e.g., out of VRAM), the system executes a safe fallback, packaging the original downloaded files without halting the assembly line.