"""
Gerador automático de podcast com DOIS APRESENTADORES.

Funcionamento:

1. Lê os temas de topics.json.
2. Lê podcast_state.json.
3. Seleciona o próximo tema da sequência.
4. Gemini cria uma conversa entre dois apresentadores.
5. edge-tts gera uma voz diferente para cada apresentador.
6. FFmpeg junta todas as falas em um único MP3.
7. Salva o episódio.
8. Envia o podcast para o Telegram.
9. Atualiza podcast_state.json somente depois do envio com sucesso.
"""

import os
import json
import asyncio
import datetime
import shutil
import subprocess
import tempfile

from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import edge_tts


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

# Apresentador masculino
VOZ_A = "pt-BR-AntonioNeural"

# Apresentadora feminina
VOZ_B = "pt-BR-FranciscaNeural"

# Aproximadamente 7 a 10 minutos de conversa,
# dependendo da velocidade das vozes.
PALAVRAS_ALVO = 1300

# Mantemos o modelo que já estava funcionando
MODELO_GEMINI = "gemini-flash-latest"

ARQUIVO_TEMAS = Path("topics.json")

ARQUIVO_ESTADO = Path("podcast_state.json")

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")


# ==========================================================
# NOMES DOS APRESENTADORES
# ==========================================================

NOMES_APRESENTADORES = {
    "A": "Apresentador 1",
    "B": "Apresentadora 2"
}


VOZES = {
    "A": VOZ_A,
    "B": VOZ_B
}


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
    ) as arquivo:

        dados = json.load(arquivo)

    temas = dados.get("temas", [])

    if not isinstance(temas, list):

        raise ValueError(
            "O campo 'temas' precisa ser uma lista."
        )

    temas = [

        str(tema).strip()

        for tema in temas

        if str(tema).strip()
    ]

    if not temas:

        raise ValueError(
            "Nenhum tema válido foi encontrado."
        )

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
        ) as arquivo:

            dados = json.load(arquivo)

        if not isinstance(dados, dict):

            raise ValueError(
                "Estado inválido."
            )

        return dados

    except Exception as erro:

        print("")
        print(
            "AVISO: não foi possível ler "
            "podcast_state.json."
        )

        print(
            f"Motivo: {erro}"
        )

        print(
            "A sequência será iniciada "
            "novamente."
        )

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None
        }


# ==========================================================
# ESCOLHER O PRÓXIMO TEMA
# ==========================================================

def escolher_proximo_tema(
    temas,
    estado
):

    ultimo_tema = estado.get(
        "ultimo_tema"
    )

    if ultimo_tema in temas:

        indice_anterior = temas.index(
            ultimo_tema
        )

        indice = (
            indice_anterior + 1
        ) % len(temas)

    else:

        # Primeira execução
        indice = 0

    tema = temas[indice]

    return indice, tema


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
    ) as arquivo:

        json.dump(
            estado,
            arquivo,
            ensure_ascii=False,
            indent=2
        )

    print("")
    print(
        "Controle de sequência atualizado."
    )

    print(
        f"Último tema enviado: {tema}"
    )


# ==========================================================
# EXTRAIR JSON DA RESPOSTA DO GEMINI
# ==========================================================

def limpar_json_gemini(
    texto
):

    texto = texto.strip()

    # Proteção caso o Gemini ainda coloque
    # ```json no começo da resposta.

    if texto.startswith("```"):

        linhas = texto.splitlines()

        if linhas and linhas[0].startswith("```"):

            linhas = linhas[1:]

        if (
            linhas
            and linhas[-1].strip() == "```"
        ):

            linhas = linhas[:-1]

        texto = "\n".join(linhas)

    return texto.strip()


# ==========================================================
# GERAR DIÁLOGO NO GEMINI
# ==========================================================

def gerar_dialogo(
    tema
):

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
Você vai criar o roteiro de um podcast brasileiro
com DOIS APRESENTADORES conversando entre si.

TEMA:

"{tema}"


OBJETIVO:

Produza aproximadamente {PALAVRAS_ALVO} palavras no total.

O podcast deve parecer uma conversa verdadeira,
interessante e dinâmica, semelhante a dois
apresentadores discutindo e explicando um assunto.


APRESENTADORES:

A = apresentador principal masculino.

B = apresentadora feminina que participa ativamente
da conversa.


ESTILO:

- Conversa natural.
- Português do Brasil.
- Linguagem clara.
- Não parecer leitura de apostila.
- Não parecer entrevista formal.
- Os dois precisam demonstrar conhecimento.
- B não deve apenas fazer perguntas.
- Os dois podem explicar conceitos.
- Um pode complementar o raciocínio do outro.
- Um pode discordar ou fazer contraponto.
- Pode haver perguntas espontâneas.
- Pode haver pequenas reações naturais.
- Pode haver exemplos.
- Pode haver analogias.
- Evite exagerar em expressões como "Nossa!",
  "Uau!" ou similares.
- Evite repetir constantemente o nome do outro
  apresentador.


QUANDO O TEMA FOR DE CONCURSO OU PRF:

- Explique pensando em alguém estudando para prova.
- Mostre pegadinhas comuns.
- Traga situações práticas.
- Explique como o assunto pode aparecer em questões.
- Quando fizer sentido, mencione o estilo Cebraspe.
- Não invente legislação.
- Não invente artigos.
- Não invente jurisprudência.
- Não invente decisões judiciais.
- Se não tiver segurança sobre um número de artigo,
  explique o conceito sem citar o número.


ESTRUTURA DA CONVERSA:

A deve começar o episódio.

Depois os apresentadores devem alternar naturalmente.

Não precisa obrigatoriamente ser:

A
B
A
B
A
B

Se fizer sentido, A pode falar duas vezes,
ou B pode desenvolver um raciocínio maior.

Mas os dois precisam participar bastante.


TAMANHO DAS FALAS:

Cada fala deve ter normalmente entre
1 e 4 frases.

Evite blocos enormes de texto para apenas
um apresentador.


ABERTURA:

Comece com uma pergunta, situação ou provocação
interessante relacionada ao tema.

Não diga:

"Bem-vindos ao nosso podcast".


FINAL:

Faça uma conclusão útil.

Os dois apresentadores podem participar
do encerramento.


IMPORTANTE:

Retorne SOMENTE um JSON válido.

Não coloque explicações antes.

Não coloque explicações depois.

Não use Markdown.

Não use ```json.


FORMATO EXATO:

{{
  "falas": [
    {{
      "speaker": "A",
      "text": "Texto falado pelo apresentador A."
    }},
    {{
      "speaker": "B",
      "text": "Texto falado pela apresentadora B."
    }}
  ]
}}

Use somente:

"A"

ou

"B"

no campo speaker.
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

        ],

        "generationConfig": {

            "temperature": 0.8,

            "maxOutputTokens": 6000,

            "responseMimeType":
                "application/json"
        }
    }


    print("")
    print(
        "Solicitando conversa ao Gemini..."
    )


    resposta = requests.post(

        url,

        json=corpo,

        timeout=180
    )


    resposta.raise_for_status()


    dados_resposta = resposta.json()


    try:

        texto_json = (

            dados_resposta[
                "candidates"
            ][0][
                "content"
            ][
                "parts"
            ][0][
                "text"
            ]

        )

    except Exception as erro:

        print("")
        print(
            "Resposta inesperada do Gemini:"
        )

        print(
            dados_resposta
        )

        raise RuntimeError(
            "Não foi possível obter "
            "o conteúdo do Gemini."
        ) from erro


    texto_json = limpar_json_gemini(
        texto_json
    )


    try:

        dialogo_json = json.loads(
            texto_json
        )

    except json.JSONDecodeError as erro:

        print("")
        print(
            "JSON recebido do Gemini:"
        )

        print(
            texto_json
        )

        raise RuntimeError(
            "Gemini não retornou "
            "um JSON válido."
        ) from erro


    # Aceita tanto:
    #
    # {"falas": [...]}
    #
    # como proteção adicional caso
    # a API retorne diretamente uma lista.

    if isinstance(
        dialogo_json,
        list
    ):

        falas = dialogo_json

    else:

        falas = dialogo_json.get(
            "falas",
            []
        )


    if not isinstance(
        falas,
        list
    ):

        raise RuntimeError(
            "A resposta do Gemini "
            "não contém uma lista de falas."
        )


    falas_validas = []


    for fala in falas:

        if not isinstance(
            fala,
            dict
        ):

            continue


        speaker = str(
            fala.get(
                "speaker",
                ""
            )
        ).strip().upper()


        texto = str(
            fala.get(
                "text",
                ""
            )
        ).strip()


        if speaker not in (
            "A",
            "B"
        ):

            continue


        if not texto:

            continue


        falas_validas.append(

            {

                "speaker": speaker,

                "text": texto
            }

        )


    if len(
        falas_validas
    ) < 4:

        raise RuntimeError(
            "Gemini retornou poucas "
            "falas válidas para o podcast."
        )


    print("")
    print(
        f"Diálogo criado com "
        f"{len(falas_validas)} falas."
    )


    return falas_validas


# ==========================================================
# SALVAR ROTEIRO LEGÍVEL
# ==========================================================

def salvar_roteiro(
    falas,
    tema,
    caminho
):

    linhas = []

    linhas.append(
        f"# Tema\n\n{tema}\n"
    )


    for fala in falas:

        speaker = fala[
            "speaker"
        ]

        texto = fala[
            "text"
        ]

        nome = NOMES_APRESENTADORES[
            speaker
        ]

        linhas.append(
            f"## {nome}\n\n{texto}\n"
        )


    caminho.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8"
    )


# ==========================================================
# GERAR UMA FALA EM ÁUDIO
# ==========================================================

async def gerar_fala_audio(
    texto,
    voz,
    caminho
):

    ultimo_erro = None


    # Faz até 3 tentativas porque
    # o serviço de voz pode eventualmente
    # apresentar erro temporário.

    for tentativa in range(
        1,
        4
    ):

        try:

            comunicador = edge_tts.Communicate(
                texto,
                voz
            )

            await comunicador.save(
                str(caminho)
            )


            if (
                caminho.exists()
                and caminho.stat().st_size > 1000
            ):

                return


            raise RuntimeError(
                "Arquivo de áudio vazio "
                "ou muito pequeno."
            )


        except Exception as erro:

            ultimo_erro = erro


            print(
                f"Tentativa {tentativa} "
                f"falhou: {erro}"
            )


            if tentativa < 3:

                await asyncio.sleep(
                    tentativa * 2
                )


    raise RuntimeError(
        "Não foi possível gerar "
        "uma das falas."
    ) from ultimo_erro


# ==========================================================
# GERAR TODOS OS SEGMENTOS
# ==========================================================

async def gerar_segmentos(
    falas,
    pasta_temporaria
):

    arquivos = []


    total = len(
        falas
    )


    for numero, fala in enumerate(
        falas,
        start=1
    ):

        speaker = fala[
            "speaker"
        ]

        texto = fala[
            "text"
        ]

        voz = VOZES[
            speaker
        ]


        caminho = (

            pasta_temporaria

            / f"fala_{numero:03d}_{speaker}.mp3"
        )


        nome = NOMES_APRESENTADORES[
            speaker
        ]


        print(
            f"Gerando fala "
            f"{numero}/{total} "
            f"- {nome}"
        )


        await gerar_fala_audio(
            texto,
            voz,
            caminho
        )


        arquivos.append(
            caminho
        )


    return arquivos


# ==========================================================
# JUNTAR TODOS OS MP3 COM FFMPEG
# ==========================================================

def juntar_audios(
    arquivos,
    caminho_final,
    pasta_temporaria
):

    if shutil.which(
        "ffmpeg"
    ) is None:

        raise RuntimeError(
            "FFmpeg não foi encontrado."
        )


    arquivo_lista = (

        pasta_temporaria

        / "lista_ffmpeg.txt"
    )


    linhas = []


    for arquivo in arquivos:

        caminho_absoluto = (
            arquivo
            .resolve()
            .as_posix()
        )


        linhas.append(
            f"file '{caminho_absoluto}'"
        )


    arquivo_lista.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8"
    )


    print("")
    print(
        "Juntando as vozes "
        "em um único podcast..."
    )


    comando = [

        "ffmpeg",

        "-y",

        "-hide_banner",

        "-loglevel",
        "error",

        "-f",
        "concat",

        "-safe",
        "0",

        "-i",
        str(
            arquivo_lista
        ),

        "-vn",

        "-c:a",
        "libmp3lame",

        "-b:a",
        "128k",

        str(
            caminho_final
        )
    ]


    subprocess.run(

        comando,

        check=True
    )


    if (
        not caminho_final.exists()
        or caminho_final.stat().st_size < 5000
    ):

        raise RuntimeError(
            "O podcast final "
            "não foi gerado corretamente."
        )


    print(
        f"Podcast final criado: "
        f"{caminho_final}"
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

        f"👥 Dois apresentadores\n\n"

        f"*Tema {numero_tema}/{total_temas}:*\n"

        f"{tema}\n\n"

        f"🔗 {link_repo}"

    )


    print("")
    print(
        "Enviando podcast "
        "para o Telegram..."
    )


    with open(
        caminho_audio,
        "rb"
    ) as audio_file:

        resposta = requests.post(

            url,

            data={

                "chat_id":
                    chat_id,

                "caption":
                    legenda,

                "parse_mode":
                    "Markdown"
            },

            files={

                "audio":
                    audio_file
            },

            timeout=180
        )


    resposta.raise_for_status()


    dados = resposta.json()


    if not dados.get(
        "ok"
    ):

        raise RuntimeError(
            f"Telegram retornou erro: {dados}"
        )


    print("")
    print(
        "Podcast enviado "
        "para o Telegram com sucesso."
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    agora = datetime.datetime.now(
        FUSO_BRASILIA
    )


    print("")
    print(
        "=" * 70
    )

    print(
        "PODCAST AUTOMÁTICO "
        "- DOIS APRESENTADORES"
    )

    print(
        "=" * 70
    )


    print(

        "Horário de Brasília:",

        agora.strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )


    # ======================================================
    # TEMA
    # ======================================================

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


    print(
        tema
    )


    # ======================================================
    # PASTA DO EPISÓDIO
    # ======================================================

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
        f"Pasta do episódio: "
        f"{pasta_episodio}"
    )


    # ======================================================
    # GERAR DIÁLOGO
    # ======================================================

    falas = gerar_dialogo(
        tema
    )


    # ======================================================
    # SALVAR ROTEIRO
    # ======================================================

    caminho_roteiro = (

        pasta_episodio

        / "roteiro.md"
    )


    salvar_roteiro(

        falas,

        tema,

        caminho_roteiro
    )


    print("")
    print(
        f"Roteiro salvo em: "
        f"{caminho_roteiro}"
    )


    # ======================================================
    # SALVAR JSON DO DIÁLOGO
    # ======================================================

    caminho_dialogo = (

        pasta_episodio

        / "dialogo.json"
    )


    caminho_dialogo.write_text(

        json.dumps(

            {
                "tema": tema,
                "falas": falas
            },

            ensure_ascii=False,

            indent=2
        ),

        encoding="utf-8"
    )


    # ======================================================
    # DADOS DO EPISÓDIO
    # ======================================================

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

        "apresentador_a":
            VOZ_A,

        "apresentador_b":
            VOZ_B,

        "quantidade_falas":
            len(falas),

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


    # ======================================================
    # GERAR ÁUDIO
    # ======================================================

    caminho_audio = (

        pasta_episodio

        / "podcast.mp3"
    )


    # Os MP3 individuais ficam apenas
    # temporariamente e NÃO são enviados
    # para o GitHub.

    with tempfile.TemporaryDirectory(
        prefix="podcast_falas_"
    ) as pasta_temp:

        pasta_temporaria = Path(
            pasta_temp
        )


        arquivos_segmentos = asyncio.run(

            gerar_segmentos(

                falas,

                pasta_temporaria
            )

        )


        juntar_audios(

            arquivos_segmentos,

            caminho_audio,

            pasta_temporaria
        )


    # ======================================================
    # LINK DO GITHUB
    # ======================================================

    repo = os.environ.get(

        "GITHUB_REPOSITORY",

        "SEU_USUARIO/SEU_REPO"
    )


    link_repo = (

        f"https://github.com/"

        f"{repo}"

        f"/tree/main/episodes/"

        f"{data}/{horario}"

    )


    # ======================================================
    # TELEGRAM
    # ======================================================

    enviar_para_telegram(

        str(
            caminho_audio
        ),

        tema,

        link_repo,

        indice + 1,

        len(
            temas
        )
    )


    # ======================================================
    # ATUALIZAR SEQUÊNCIA
    #
    # SOMENTE DEPOIS DO TELEGRAM
    # CONFIRMAR O ENVIO.
    # ======================================================

    salvar_estado(

        indice,

        tema,

        agora
    )


    print("")
    print(
        "=" * 70
    )

    print(
        "PROCESSO CONCLUÍDO "
        "COM SUCESSO"
    )

    print(
        "=" * 70
    )

    print("")


if __name__ == "__main__":

    main()