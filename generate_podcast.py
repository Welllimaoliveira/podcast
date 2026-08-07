"""
Gerador automático de podcast.

Funcionamento:
1. Lê os temas do topics.json.
2. Consulta podcast_state.json para descobrir o último tema enviado.
3. Seleciona o PRÓXIMO tema.
4. Gera o roteiro com Gemini.
5. Gera o MP3 com edge-tts.
6. Salva em episodes/AAAA-MM-DD/HH-MM-SS/
7. Envia para o Telegram.
8. Atualiza podcast_state.json somente se o envio der certo.
"""

import os
import json
import asyncio
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import edge_tts


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

VOZ = "pt-BR-AntonioNeural"

PALAVRAS_ALVO = 1500

MODELO_GEMINI = "gemini-flash-latest"

ARQUIVO_TEMAS = Path("topics.json")

ARQUIVO_ESTADO = Path("podcast_state.json")

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


# ==========================================================
# CARREGAR TEMAS
# ==========================================================

def carregar_temas():

    if not ARQUIVO_TEMAS.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_TEMAS}"
        )

    with open(
        ARQUIVO_TEMAS,
        "r",
        encoding="utf-8"
    ) as f:

        dados = json.load(f)

    temas = dados.get("temas", [])

    if not temas:
        raise ValueError(
            "Nenhum tema encontrado em topics.json"
        )

    # Remove linhas vazias
    temas = [
        str(tema).strip()
        for tema in temas
        if str(tema).strip()
    ]

    return temas


# ==========================================================
# CARREGAR ESTADO
# ==========================================================

def carregar_estado():

    if not ARQUIVO_ESTADO.exists():

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None
        }

    try:

        with open(
            ARQUIVO_ESTADO,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception:

        print(
            "Estado inválido. "
            "Reiniciando a sequência."
        )

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None
        }


# ==========================================================
# ESCOLHER PRÓXIMO TEMA
# ==========================================================

def escolher_proximo_tema(temas, estado):

    ultimo_tema = estado.get("ultimo_tema")

    # Se já existe um último tema,
    # localiza ele dentro da lista.
    if ultimo_tema in temas:

        indice_atual = temas.index(ultimo_tema)

        proximo_indice = (
            indice_atual + 1
        ) % len(temas)

    else:

        # Primeira execução
        proximo_indice = 0

    tema = temas[proximo_indice]

    return proximo_indice, tema


# ==========================================================
# SALVAR ESTADO
# ==========================================================

def salvar_estado(
    indice,
    tema,
    agora
):

    estado = {

        "ultimo_indice": indice,

        "ultimo_tema": tema,

        "ultima_execucao":
            agora.isoformat()
    }

    with open(
        ARQUIVO_ESTADO,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            estado,
            f,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print("Estado atualizado.")
    print(f"Último tema enviado: {tema}")


# ==========================================================
# GERAR ROTEIRO NO GEMINI
# ==========================================================

def gerar_roteiro(tema):

    api_key = os.environ[
        "GEMINI_API_KEY"
    ]

    url = (

        "https://generativelanguage.googleapis.com/"
        "v1beta/models/"
        f"{MODELO_GEMINI}:generateContent"
        f"?key={api_key}"

    )

    prompt = f"""
Escreva o roteiro de um episódio de podcast em português do Brasil,
com aproximadamente {PALAVRAS_ALVO} palavras.

Tema do episódio:

"{tema}"

Regras:

- Fale como se fosse UM apresentador só.
- Use tom natural e conversacional.
- Explique como se estivesse conversando com alguém que está estudando.
- Quando o assunto estiver relacionado à PRF, dê preferência para exemplos de concurso e situações práticas.
- Comece com uma abertura curta e interessante.
- Explique os conceitos de forma clara.
- Traga exemplos concretos.
- Quando envolver legislação, não invente artigos, regras ou decisões.
- NÃO use marcações como [música], [pausa] ou similares.
- NÃO coloque títulos no meio do texto.
- NÃO utilize formatação Markdown.
- Gere apenas o texto que será transformado em voz.
- Termine com uma despedida breve.
"""

    corpo = {

        "contents": [

            {

                "parts": [

                    {
                        "text": prompt
                    }

                ]

            }

        ]

    }

    print("")
    print("Solicitando roteiro ao Gemini...")

    resposta = requests.post(
        url,
        json=corpo,
        timeout=120
    )

    resposta.raise_for_status()

    dados = resposta.json()

    try:

        roteiro = (
            dados["candidates"][0]
            ["content"]
            ["parts"][0]
            ["text"]
            .strip()
        )

    except Exception as erro:

        print("")
        print("Resposta recebida do Gemini:")
        print(dados)

        raise RuntimeError(
            "Não foi possível interpretar "
            "a resposta do Gemini."
        ) from erro

    if not roteiro:

        raise RuntimeError(
            "Gemini retornou roteiro vazio."
        )

    return roteiro


# ==========================================================
# CONVERTER TEXTO PARA ÁUDIO
# ==========================================================

async def texto_para_audio(
    texto,
    caminho_saida
):

    comunicador = edge_tts.Communicate(
        texto,
        VOZ
    )

    await comunicador.save(
        caminho_saida
    )


# ==========================================================
# ENVIAR PARA TELEGRAM
# ==========================================================

def enviar_para_telegram(
    caminho_audio,
    tema,
    link_repo,
    numero_tema,
    total_temas
):

    token = os.environ[
        "TELEGRAM_BOT_TOKEN"
    ]

    chat_id = os.environ[
        "TELEGRAM_CHAT_ID"
    ]

    url = (
        f"https://api.telegram.org/"
        f"bot{token}/sendAudio"
    )

    legenda = (

        "🎙️ Podcast de Estudos\n\n"

        f"*Tema {numero_tema}/{total_temas}:*\n"

        f"{tema}\n\n"

        f"🔗 {link_repo}"

    )

    print("")
    print("Enviando podcast para Telegram...")

    with open(
        caminho_audio,
        "rb"
    ) as audio_file:

        resposta = requests.post(

            url,

            data={
                "chat_id": chat_id,
                "caption": legenda,
                "parse_mode": "Markdown"
            },

            files={
                "audio": audio_file
            },

            timeout=120
        )

    resposta.raise_for_status()

    dados = resposta.json()

    if not dados.get("ok"):

        raise RuntimeError(
            f"Telegram retornou erro: {dados}"
        )

    print("")
    print(
        "Podcast enviado para "
        "o Telegram com sucesso."
    )


# ==========================================================
# PROGRAMA PRINCIPAL
# ==========================================================

def main():

    agora = datetime.datetime.now(
        FUSO_BRASILIA
    )

    print("")
    print("=" * 70)
    print("PODCAST AUTOMÁTICO")
    print("=" * 70)

    print(
        "Horário de Brasília:",
        agora.strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )

    # ------------------------------------------------------
    # TEMAS
    # ------------------------------------------------------

    temas = carregar_temas()

    estado = carregar_estado()

    indice, tema = escolher_proximo_tema(
        temas,
        estado
    )

    print("")
    print(
        f"Tema selecionado: "
        f"{indice + 1}/{len(temas)}"
    )

    print(tema)

    # ------------------------------------------------------
    # CRIAR PASTA DO EPISÓDIO
    # ------------------------------------------------------

    data = agora.strftime(
        "%Y-%m-%d"
    )

    horario = agora.strftime(
        "%H-%M-%S"
    )

    pasta_episodio = (
        Path("episodes")
        / data
        / horario
    )

    pasta_episodio.mkdir(
        parents=True,
        exist_ok=True
    )

    print("")
    print(
        "Pasta:",
        pasta_episodio
    )

    # ------------------------------------------------------
    # GERAR ROTEIRO
    # ------------------------------------------------------

    roteiro = gerar_roteiro(
        tema
    )

    caminho_roteiro = (
        pasta_episodio
        / "roteiro.md"
    )

    caminho_roteiro.write_text(
        roteiro,
        encoding="utf-8"
    )

    print("")
    print(
        "Roteiro salvo em:",
        caminho_roteiro
    )

    # ------------------------------------------------------
    # SALVAR INFORMAÇÕES DO EPISÓDIO
    # ------------------------------------------------------

    dados_episodio = {

        "data_hora_brasilia":
            agora.isoformat(),

        "indice_tema":
            indice,

        "numero_tema":
            indice + 1,

        "total_temas":
            len(temas),

        "tema":
            tema,

        "voz":
            VOZ,

        "modelo_gemini":
            MODELO_GEMINI
    }

    caminho_info = (
        pasta_episodio
        / "episodio.json"
    )

    caminho_info.write_text(

        json.dumps(
            dados_episodio,
            ensure_ascii=False,
            indent=2
        ),

        encoding="utf-8"
    )

    # ------------------------------------------------------
    # GERAR ÁUDIO
    # ------------------------------------------------------

    caminho_audio = (
        pasta_episodio
        / "podcast.mp3"
    )

    print("")
    print("Gerando áudio...")

    asyncio.run(

        texto_para_audio(
            roteiro,
            str(caminho_audio)
        )

    )

    print(
        "Áudio salvo em:",
        caminho_audio
    )

    # ------------------------------------------------------
    # LINK DO GITHUB
    # ------------------------------------------------------

    repo = os.environ.get(
        "GITHUB_REPOSITORY",
        "SEU_USUARIO/SEU_REPO"
    )

    link_repo = (

        f"https://github.com/"
        f"{repo}/tree/main/"
        f"episodes/{data}/{horario}"

    )

    # ------------------------------------------------------
    # TELEGRAM
    # ------------------------------------------------------

    enviar_para_telegram(

        str(caminho_audio),

        tema,

        link_repo,

        indice + 1,

        len(temas)

    )

    # ------------------------------------------------------
    # SOMENTE DEPOIS DO TELEGRAM TER FUNCIONADO
    # AVANÇA PARA O PRÓXIMO TEMA
    # ------------------------------------------------------

    salvar_estado(
        indice,
        tema,
        agora
    )

    print("")
    print("=" * 70)
    print(
        "PROCESSO CONCLUÍDO COM SUCESSO"
    )
    print("=" * 70)
    print("")


if __name__ == "__main__":
    main()