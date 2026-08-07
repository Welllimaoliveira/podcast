"""
Gerador automático de podcast com DOIS APRESENTADORES.

Fluxo:
1. Lê os temas em topics.json.
2. Lê podcast_state.json.
3. Seleciona o próximo tema da sequência.
4. Gera um diálogo estruturado com Gemini.
5. Gera as falas com duas vozes do edge-tts.
6. Junta as falas com FFmpeg em um único MP3.
7. Salva roteiro, diálogo e metadados.
8. Envia o MP3 para o Telegram.
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

VOZ_A = "pt-BR-AntonioNeural"
VOZ_B = "pt-BR-FranciscaNeural"

# Valor aproximado.
# Se o Gemini cortar a resposta, o sistema tenta
# automaticamente com 850 e depois 700 palavras.
PALAVRAS_ALVO = 1000

MODELO_GEMINI = "gemini-flash-latest"

ARQUIVO_TEMAS = Path("topics.json")
ARQUIVO_ESTADO = Path("podcast_state.json")

FUSO_BRASILIA = ZoneInfo("America/Sao_Paulo")

NOMES_APRESENTADORES = {
    "A": "Apresentador 1",
    "B": "Apresentadora 2",
}

VOZES = {
    "A": VOZ_A,
    "B": VOZ_B,
}


# ==========================================================
# TEMAS
# ==========================================================

def carregar_temas():

    if not ARQUIVO_TEMAS.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: {ARQUIVO_TEMAS}"
        )

    with ARQUIVO_TEMAS.open(
        "r",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(
            arquivo
        )

    temas = dados.get(
        "temas",
        []
    )

    if not isinstance(
        temas,
        list
    ):

        raise ValueError(
            "O campo 'temas' do topics.json "
            "precisa ser uma lista."
        )

    temas = [

        str(tema).strip()

        for tema in temas

        if str(tema).strip()
    ]

    if not temas:

        raise ValueError(
            "Nenhum tema válido foi encontrado "
            "em topics.json."
        )

    return temas


# ==========================================================
# ESTADO
# ==========================================================

def carregar_estado():

    if not ARQUIVO_ESTADO.exists():

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None,
        }

    try:

        with ARQUIVO_ESTADO.open(
            "r",
            encoding="utf-8"
        ) as arquivo:

            estado = json.load(
                arquivo
            )

        if not isinstance(
            estado,
            dict
        ):

            raise ValueError(
                "podcast_state.json inválido."
            )

        return estado

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
            "A sequência será reiniciada "
            "a partir do primeiro tema."
        )

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None,
        }


# ==========================================================
# PRÓXIMO TEMA
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
        ) % len(
            temas
        )

    else:

        indice = 0

    return (
        indice,
        temas[indice]
    )


# ==========================================================
# SALVAR ESTADO
# ==========================================================

def salvar_estado(
    indice,
    tema,
    agora
):

    estado = {

        "ultimo_indice":
            indice,

        "ultimo_tema":
            tema,

        "ultima_execucao":
            agora.isoformat(),
    }

    with ARQUIVO_ESTADO.open(
        "w",
        encoding="utf-8"
    ) as arquivo:

        json.dump(
            estado,
            arquivo,
            ensure_ascii=False,
            indent=2,
        )

    print("")
    print(
        "Controle de sequência atualizado."
    )

    print(
        f"Último tema enviado: {tema}"
    )


# ==========================================================
# LIMPAR JSON DO GEMINI
# ==========================================================

def limpar_json_gemini(
    texto
):

    texto = texto.strip()

    # Caso o Gemini ainda retorne:
    #
    # ```json
    # {...}
    # ```

    if texto.startswith(
        "```"
    ):

        linhas = texto.splitlines()

        if (
            linhas
            and linhas[0].startswith("```")
        ):

            linhas = linhas[1:]

        if (
            linhas
            and linhas[-1].strip() == "```"
        ):

            linhas = linhas[:-1]

        texto = "\n".join(
            linhas
        )

    return texto.strip()


# ==========================================================
# VALIDAR RESPOSTA GEMINI
# ==========================================================

def extrair_falas_resposta_gemini(
    dados_resposta
):

    candidatos = dados_resposta.get(
        "candidates",
        []
    )

    if not candidatos:

        raise RuntimeError(
            "Gemini não retornou candidatos. "
            f"Resposta: {dados_resposta}"
        )

    candidato = candidatos[0]

    finish_reason = candidato.get(
        "finishReason",
        "DESCONHECIDO"
    )

    print(
        f"Finish reason do Gemini: "
        f"{finish_reason}"
    )

    partes = (
        candidato
        .get(
            "content",
            {}
        )
        .get(
            "parts",
            []
        )
    )

    if not partes:

        raise RuntimeError(
            "Gemini retornou resposta "
            "sem conteúdo."
        )

    texto_json = partes[0].get(
        "text",
        ""
    )

    texto_json = limpar_json_gemini(
        texto_json
    )

    # Caso o Gemini informe explicitamente
    # que atingiu o limite de tokens.

    if finish_reason == "MAX_TOKENS":

        raise RuntimeError(
            "MAX_TOKENS"
        )

    try:

        dialogo_json = json.loads(
            texto_json
        )

    except json.JSONDecodeError as erro:

        print("")
        print(
            "O Gemini retornou JSON "
            "incompleto ou inválido."
        )

        print("")
        print(
            "Últimos 500 caracteres "
            "recebidos:"
        )

        print(
            texto_json[-500:]
        )

        raise RuntimeError(
            "JSON_INCOMPLETO"
        ) from erro

    # Proteção adicional:
    # aceita tanto:
    #
    # {"falas": [...]}
    #
    # quanto uma lista direta.

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
            "O campo 'falas' "
            "não é uma lista."
        )

    falas_validas = []

    for fala in falas:

        # Ignora:
        #
        # {}
        #
        # ou qualquer item inválido.

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
                "speaker":
                    speaker,

                "text":
                    texto,
            }

        )

    if len(
        falas_validas
    ) < 8:

        raise RuntimeError(

            f"Gemini retornou poucas "
            f"falas válidas: "
            f"{len(falas_validas)}."
        )

    return falas_validas


# ==========================================================
# PROMPT
# ==========================================================

def montar_prompt(
    tema,
    palavras
):

    return f"""
Crie um roteiro de podcast em português do Brasil
com DOIS APRESENTADORES conversando naturalmente.

TEMA:

"{tema}"


TAMANHO:

O roteiro inteiro deve ter aproximadamente
{palavras} palavras.

Não ultrapasse muito esse tamanho.


APRESENTADORES:

A = apresentador masculino.

B = apresentadora feminina.


OBJETIVO:

A conversa deve parecer um podcast real,
com duas pessoas discutindo, explicando
e complementando o assunto juntas.


ESTILO:

- Português brasileiro natural.
- Conversa dinâmica.
- Não parecer leitura de apostila.
- Não parecer uma entrevista formal.
- Os dois precisam demonstrar conhecimento.
- B não deve apenas fazer perguntas.
- Os dois devem explicar conceitos.
- Um pode complementar o outro.
- Um pode fazer perguntas.
- Um pode apresentar contrapontos.
- Pode haver exemplos.
- Pode haver analogias.
- Pode haver pequenas reações naturais.
- Evite exagerar em expressões como
  "Nossa!", "Uau!" ou similares.
- Não repita constantemente o nome
  do outro apresentador.
- Evite blocos enormes de texto
  para apenas uma pessoa.


FALAS:

Faça aproximadamente entre
22 e 30 falas.

Cada fala deve ter normalmente
entre 1 e 3 frases.

O apresentador A deve começar.

A alternância precisa parecer natural.


QUANDO O TEMA FOR DE CONCURSO OU PRF:

- Pense em quem está estudando para prova.
- Explique pegadinhas comuns.
- Traga exemplos práticos.
- Mostre como o assunto pode aparecer
  em questões.
- Quando fizer sentido,
  mencione o estilo Cebraspe.
- Não invente legislação.
- Não invente artigos.
- Não invente jurisprudência.
- Não invente decisões judiciais.
- Se não tiver certeza sobre um número
  de artigo, explique o conceito
  sem citar o número.


FINAL:

Faça um encerramento natural e útil.

Os dois apresentadores podem participar
da conclusão.


FORMATO OBRIGATÓRIO:

Retorne SOMENTE JSON válido.

Não escreva nada antes do JSON.

Não escreva nada depois do JSON.

Não utilize Markdown.

Não utilize blocos ```json.


Formato esperado:

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


O campo "speaker" pode conter SOMENTE:

"A"

ou

"B"
"""


# ==========================================================
# GERAR DIÁLOGO COM RETENTATIVAS
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

    # Caso a primeira resposta fique grande
    # demais e seja cortada, tentamos
    # automaticamente com um roteiro menor.

    tentativas_palavras = [

        1000,

        850,

        700,
    ]

    ultimo_erro = None

    for numero_tentativa, palavras in enumerate(

        tentativas_palavras,

        start=1

    ):

        print("")
        print(
            f"Solicitando conversa ao Gemini "
            f"- tentativa "
            f"{numero_tentativa}/"
            f"{len(tentativas_palavras)}"
        )

        print(
            f"Tamanho solicitado: "
            f"aproximadamente "
            f"{palavras} palavras."
        )

        prompt = montar_prompt(
            tema,
            palavras
        )

        corpo = {

            "contents": [

                {

                    "parts": [

                        {
                            "text":
                                prompt
                        }

                    ]

                }

            ],

            "generationConfig": {

                "temperature":
                    0.75,

                # Mais espaço para evitar
                # corte prematuro da resposta.

                "maxOutputTokens":
                    8192,

                # Obriga a API a trabalhar
                # como JSON.

                "responseMimeType":
                    "application/json",

                # Esquema estruturado.
                #
                # Ajuda a impedir objetos vazios
                # como {}.

                "responseSchema": {

                    "type":
                        "OBJECT",

                    "properties": {

                        "falas": {

                            "type":
                                "ARRAY",

                            "items": {

                                "type":
                                    "OBJECT",

                                "properties": {

                                    "speaker": {

                                        "type":
                                            "STRING",

                                        "enum": [
                                            "A",
                                            "B"
                                        ],
                                    },

                                    "text": {

                                        "type":
                                            "STRING",
                                    },
                                },

                                "required": [

                                    "speaker",

                                    "text",
                                ],
                            },
                        }
                    },

                    "required": [

                        "falas"
                    ],
                },
            },
        }

        try:

            resposta = requests.post(

                url,

                json=corpo,

                timeout=180
            )

            resposta.raise_for_status()

            dados_resposta = resposta.json()

            falas = extrair_falas_resposta_gemini(
                dados_resposta
            )

            print("")
            print(

                f"Diálogo criado com sucesso: "
                f"{len(falas)} falas."
            )

            return falas

        except Exception as erro:

            ultimo_erro = erro

            print("")
            print(

                f"Tentativa "
                f"{numero_tentativa} "
                f"falhou: {erro}"
            )

            if numero_tentativa < len(
                tentativas_palavras
            ):

                print("")
                print(

                    "Tentando novamente "
                    "com um roteiro menor..."
                )

    raise RuntimeError(

        "Não foi possível gerar "
        "um diálogo completo "
        "após 3 tentativas."

    ) from ultimo_erro


# ==========================================================
# SALVAR ROTEIRO LEGÍVEL
# ==========================================================

def salvar_roteiro(
    falas,
    tema,
    caminho
):

    linhas = [

        f"# Tema\n\n{tema}\n"

    ]

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

            f"## {nome}\n\n"
            f"{texto}\n"
        )

    caminho.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8"
    )


# ==========================================================
# GERAR UMA FALA
# ==========================================================

async def gerar_fala_audio(
    texto,
    voz,
    caminho
):

    ultimo_erro = None

    # Edge-TTS pode ocasionalmente
    # apresentar erro de conexão.
    #
    # Fazemos até 3 tentativas.

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

                str(
                    caminho
                )
            )

            if (

                caminho.exists()

                and

                caminho.stat().st_size > 1000

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
                f"de gerar fala falhou: "
                f"{erro}"
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
# JUNTAR MP3 COM FFMPEG
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

            "FFmpeg não foi encontrado "
            "no ambiente."
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
        ),
    ]

    subprocess.run(

        comando,

        check=True
    )

    if (

        not caminho_final.exists()

        or

        caminho_final.stat().st_size < 5000

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
# TELEGRAM
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

        "👥 Dois apresentadores\n\n"

        f"*Tema "
        f"{numero_tema}/"
        f"{total_temas}:*\n"

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
                    "Markdown",
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

            f"Telegram retornou erro: "
            f"{dados}"
        )

    print("")
    print(

        "Podcast enviado para "
        "o Telegram com sucesso."
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
        f"{indice + 1}/"
        f"{len(temas)}"
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

        Path(
            "episodes"
        )

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
    # SALVAR DIÁLOGO JSON
    # ======================================================

    caminho_dialogo = (

        pasta_episodio

        / "dialogo.json"
    )

    caminho_dialogo.write_text(

        json.dumps(

            {

                "tema":
                    tema,

                "falas":
                    falas,
            },

            ensure_ascii=False,

            indent=2
        ),

        encoding="utf-8"
    )


    # ======================================================
    # METADADOS
    # ======================================================

    dados_episodio = {

        "data_hora_brasilia":
            agora.isoformat(),

        "indice_tema":
            indice,

        "numero_tema":
            indice + 1,

        "total_temas":
            len(
                temas
            ),

        "tema":
            tema,

        "apresentador_a":
            VOZ_A,

        "apresentador_b":
            VOZ_B,

        "quantidade_falas":
            len(
                falas
            ),

        "modelo_gemini":
            MODELO_GEMINI,

        "palavras_alvo":
            PALAVRAS_ALVO,
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

    # As falas individuais ficam
    # somente em uma pasta temporária.
    #
    # Elas NÃO são enviadas ao GitHub.

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

        f"{data}/"

        f"{horario}"
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
    # ATUALIZAR ESTADO
    #
    # IMPORTANTE:
    #
    # somente atualiza após o Telegram
    # confirmar o envio.
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