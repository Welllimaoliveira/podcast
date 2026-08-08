"""
PODCAST AUTOMÁTICO COM DOIS APRESENTADORES
GERAÇÃO EM 3 PARTES PARA EPISÓDIOS DE ~20 MINUTOS

Fluxo:

1. Lê os temas em topics.json.
2. Lê podcast_state.json.
3. Seleciona o próximo tema da sequência.
4. Gemini cria um planejamento do episódio.
5. Gemini gera PARTE 1.
6. Gemini recebe o final da PARTE 1 e gera PARTE 2.
7. Gemini recebe o final da PARTE 2 e gera PARTE 3.
8. Todas as falas são reunidas.
9. edge-tts gera as duas vozes.
10. FFmpeg junta todas as falas em um único MP3.
11. O episódio é enviado ao Telegram.
12. podcast_state.json só avança depois do envio com sucesso.

Objetivo aproximado:

PARTE 1 = ~1.100 palavras
PARTE 2 = ~1.100 palavras
PARTE 3 = ~1.100 palavras

TOTAL = ~3.300 palavras
DURAÇÃO APROXIMADA = 18 a 22 minutos
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
# CONFIGURAÇÕES GERAIS
# ==========================================================

# Voz masculina
VOZ_A = "pt-BR-AntonioNeural"

# Voz feminina
VOZ_B = "pt-BR-FranciscaNeural"

# Modelo Gemini
MODELO_GEMINI = "gemini-flash-latest"

# Número de partes do episódio
QUANTIDADE_PARTES = 3

# Tamanho principal de cada parte
PALAVRAS_POR_PARTE = 1100

# Caso uma resposta venha cortada,
# tenta novamente com tamanhos menores.
TENTATIVAS_PALAVRAS = [
    1100,
    1000,
    900,
]

# Quantas últimas falas serão enviadas
# para o Gemini como contexto da próxima parte.
FALAS_CONTEXTO = 8

# Arquivos do sistema
ARQUIVO_TEMAS = Path("topics.json")
ARQUIVO_ESTADO = Path("podcast_state.json")

# Fuso horário
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
# CARREGAR TEMAS
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

        dados = json.load(arquivo)

    temas = dados.get(
        "temas",
        []
    )

    if not isinstance(
        temas,
        list
    ):
        raise ValueError(
            "O campo 'temas' em topics.json "
            "precisa ser uma lista."
        )

    temas = [
        str(tema).strip()
        for tema in temas
        if str(tema).strip()
    ]

    if not temas:
        raise ValueError(
            "Nenhum tema válido encontrado "
            "em topics.json."
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
            "ultima_execucao": None,
        }

    try:

        with ARQUIVO_ESTADO.open(
            "r",
            encoding="utf-8"
        ) as arquivo:

            estado = json.load(arquivo)

        if not isinstance(
            estado,
            dict
        ):
            raise ValueError(
                "Estado inválido."
            )

        return estado

    except Exception as erro:

        print("")
        print(
            "AVISO: não foi possível carregar "
            "podcast_state.json."
        )

        print(
            f"Motivo: {erro}"
        )

        print(
            "A sequência será reiniciada."
        )

        return {
            "ultimo_indice": -1,
            "ultimo_tema": None,
            "ultima_execucao": None,
        }


# ==========================================================
# ESCOLHER PRÓXIMO TEMA
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

        indice = 0

    return indice, temas[indice]


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
        "ultima_execucao": agora.isoformat(),
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
# LIMPAR POSSÍVEL MARKDOWN DO GEMINI
# ==========================================================

def limpar_json_gemini(
    texto
):

    texto = texto.strip()

    if texto.startswith("```"):

        linhas = texto.splitlines()

        if linhas and linhas[0].startswith(
            "```"
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
# FAZER CHAMADA AO GEMINI
# ==========================================================

def chamar_gemini(
    prompt,
    response_schema,
    max_output_tokens=8192,
    temperature=0.75
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

            "temperature":
                temperature,

            "maxOutputTokens":
                max_output_tokens,

            "responseMimeType":
                "application/json",

            "responseSchema":
                response_schema,
        }
    }

    resposta = requests.post(
        url,
        json=corpo,
        timeout=180,
    )

    resposta.raise_for_status()

    return resposta.json()


# ==========================================================
# OBTER TEXTO DA RESPOSTA GEMINI
# ==========================================================

def obter_texto_gemini(
    dados_resposta
):

    candidatos = dados_resposta.get(
        "candidates",
        []
    )

    if not candidatos:

        raise RuntimeError(
            "Gemini não retornou candidatos."
        )

    candidato = candidatos[0]

    finish_reason = candidato.get(
        "finishReason",
        "DESCONHECIDO"
    )

    print(
        f"Finish reason: {finish_reason}"
    )

    if finish_reason == "MAX_TOKENS":

        raise RuntimeError(
            "MAX_TOKENS"
        )

    partes = (
        candidato
        .get("content", {})
        .get("parts", [])
    )

    if not partes:

        raise RuntimeError(
            "Gemini retornou resposta sem conteúdo."
        )

    texto = partes[0].get(
        "text",
        ""
    )

    if not texto:

        raise RuntimeError(
            "Gemini retornou texto vazio."
        )

    return limpar_json_gemini(
        texto
    )


# ==========================================================
# PLANEJAMENTO DO EPISÓDIO
# ==========================================================

def gerar_plano_episodio(
    tema
):

    print("")
    print("=" * 70)
    print("CRIANDO PLANEJAMENTO DO EPISÓDIO")
    print("=" * 70)

    prompt = f"""
Crie um planejamento para um podcast educacional
em português do Brasil.

Tema:

"{tema}"

O episódio terá aproximadamente 20 minutos
e será dividido internamente em 3 partes.

Essas partes serão depois unidas em um único
podcast, portanto precisam formar uma narrativa
contínua.

PARTE 1:
Introdução natural ao assunto, contexto,
fundamentos e conceitos essenciais.

PARTE 2:
Aprofundamento, exemplos, aplicações,
comparações e pegadinhas importantes.

PARTE 3:
Casos práticos, revisão dos pontos principais,
consolidação do conhecimento e conclusão.

Quando for tema relacionado a concurso ou PRF:

- Pense em quem está estudando para prova.
- Destaque pontos que podem aparecer no Cebraspe.
- Inclua situações práticas.
- Não invente legislação.
- Não invente números de artigos.
- Não invente jurisprudência.
- Não invente decisões judiciais.

Crie tópicos específicos para o tema fornecido.

Evite repetir o mesmo assunto nas três partes.

Retorne somente JSON válido.
"""

    schema = {

        "type": "OBJECT",

        "properties": {

            "parte_1": {
                "type": "STRING"
            },

            "parte_2": {
                "type": "STRING"
            },

            "parte_3": {
                "type": "STRING"
            },
        },

        "required": [
            "parte_1",
            "parte_2",
            "parte_3",
        ],
    }

    try:

        dados = chamar_gemini(
            prompt,
            schema,
            max_output_tokens=2048,
            temperature=0.55,
        )

        texto = obter_texto_gemini(
            dados
        )

        plano = json.loads(
            texto
        )

        if (
            plano.get("parte_1")
            and plano.get("parte_2")
            and plano.get("parte_3")
        ):

            print("")
            print(
                "Planejamento criado com sucesso."
            )

            return plano

    except Exception as erro:

        print("")
        print(
            "Não foi possível gerar o "
            "planejamento automático."
        )

        print(
            f"Motivo: {erro}"
        )

        print(
            "Usando planejamento padrão."
        )

    # Fallback caso a geração do plano falhe.
    return {

        "parte_1":
            (
                "Apresentar o tema, contextualizar sua "
                "importância, explicar os fundamentos "
                "e os principais conceitos necessários "
                "para compreender o assunto."
            ),

        "parte_2":
            (
                "Aprofundar os conceitos apresentados, "
                "trazer exemplos, comparações, aplicações "
                "práticas e pontos que costumam gerar "
                "confusão ou erro."
            ),

        "parte_3":
            (
                "Apresentar situações práticas, revisar "
                "os pontos fundamentais, consolidar o "
                "aprendizado e realizar um encerramento "
                "natural do episódio."
            ),
    }


# ==========================================================
# FORMATAR PLANO
# ==========================================================

def formatar_plano(
    plano
):

    return f"""
PLANEJAMENTO GERAL DO EPISÓDIO:

PARTE 1:
{plano["parte_1"]}

PARTE 2:
{plano["parte_2"]}

PARTE 3:
{plano["parte_3"]}
"""


# ==========================================================
# CRIAR CONTEXTO DA PARTE ANTERIOR
# ==========================================================

def montar_contexto_continuidade(
    falas
):

    if not falas:

        return (
            "Esta é a primeira parte do episódio. "
            "Não existe conversa anterior."
        )

    ultimas = falas[
        -FALAS_CONTEXTO:
    ]

    linhas = []

    for fala in ultimas:

        speaker = fala[
            "speaker"
        ]

        texto = fala[
            "text"
        ]

        linhas.append(
            f"{speaker}: {texto}"
        )

    return "\n".join(
        linhas
    )


# ==========================================================
# VALIDAR FALAS GERADAS
# ==========================================================

def extrair_falas(
    dados_resposta
):

    texto = obter_texto_gemini(
        dados_resposta
    )

    try:

        resposta_json = json.loads(
            texto
        )

    except json.JSONDecodeError as erro:

        print("")
        print(
            "JSON incompleto recebido."
        )

        print("")
        print(
            "Últimos 600 caracteres:"
        )

        print(
            texto[-600:]
        )

        raise RuntimeError(
            "JSON_INCOMPLETO"
        ) from erro

    falas = resposta_json.get(
        "falas",
        []
    )

    if not isinstance(
        falas,
        list
    ):

        raise RuntimeError(
            "O campo falas não é uma lista."
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

        texto_fala = str(
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

        if not texto_fala:
            continue

        falas_validas.append(
            {
                "speaker": speaker,
                "text": texto_fala,
            }
        )

    if len(
        falas_validas
    ) < 10:

        raise RuntimeError(
            f"Poucas falas válidas: "
            f"{len(falas_validas)}"
        )

    return falas_validas


# ==========================================================
# GERAR UMA DAS TRÊS PARTES
# ==========================================================

def gerar_parte(
    tema,
    numero_parte,
    plano,
    falas_anteriores
):

    contexto = montar_contexto_continuidade(
        falas_anteriores
    )

    plano_formatado = formatar_plano(
        plano
    )

    if numero_parte == 1:

        instrucao_inicio = """
Esta é a PRIMEIRA parte.

O apresentador A deve iniciar.

Faça uma abertura envolvente.

Pode começar com:
- pergunta;
- situação prática;
- curiosidade;
- problema relacionado ao tema.

Não use a frase:
"Bem-vindos ao nosso podcast".

No final desta parte não faça despedida.

Deixe a conversa pronta para continuar.
"""

    elif numero_parte == 2:

        instrucao_inicio = """
Esta é a SEGUNDA parte.

IMPORTANTE:

Continue diretamente da conversa anterior.

NÃO faça nova introdução.

NÃO diga:
- "na segunda parte";
- "voltando ao podcast";
- "agora vamos começar outro assunto";
- "bem-vindos novamente".

Não repita explicações já dadas.

A primeira fala deve parecer consequência natural
da conversa anterior.

Aprofunde o assunto conforme o planejamento.

No final não faça despedida.
"""

    else:

        instrucao_inicio = """
Esta é a TERCEIRA e última parte.

Continue diretamente da conversa anterior.

NÃO faça nova introdução.

Aprofunde os pontos restantes.

Depois faça uma revisão natural dos pontos
mais importantes.

Finalize o episódio de maneira útil e agradável.

Os dois apresentadores podem participar
do encerramento.

Somente esta parte deve ter despedida.
"""

    objetivo_parte = plano[
        f"parte_{numero_parte}"
    ]

    schema = {

        "type": "OBJECT",

        "properties": {

            "falas": {

                "type": "ARRAY",

                "items": {

                    "type": "OBJECT",

                    "properties": {

                        "speaker": {

                            "type": "STRING",

                            "enum": [
                                "A",
                                "B"
                            ],
                        },

                        "text": {
                            "type": "STRING"
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
    }

    ultimo_erro = None

    for tentativa, palavras in enumerate(
        TENTATIVAS_PALAVRAS,
        start=1
    ):

        print("")
        print(
            "=" * 70
        )

        print(
            f"GERANDO PARTE "
            f"{numero_parte}/{QUANTIDADE_PARTES}"
        )

        print(
            f"Tentativa "
            f"{tentativa}/"
            f"{len(TENTATIVAS_PALAVRAS)}"
        )

        print(
            f"Tamanho alvo: "
            f"{palavras} palavras"
        )

        print(
            "=" * 70
        )

        prompt = f"""
Crie a PARTE {numero_parte} de um podcast
com DOIS APRESENTADORES.

TEMA DO EPISÓDIO:

"{tema}"


{plano_formatado}


OBJETIVO ESPECÍFICO DESTA PARTE:

{objetivo_parte}


CONTEXTO DO FINAL DA CONVERSA ANTERIOR:

{contexto}


{instrucao_inicio}


TAMANHO:

Produza aproximadamente {palavras} palavras
nesta parte.

Não ultrapasse muito o tamanho solicitado.


PERSONAGENS:

A = apresentador masculino.

B = apresentadora feminina.


ESTILO:

- Português brasileiro natural.
- Conversa dinâmica.
- Dois apresentadores inteligentes.
- Não parecer leitura de apostila.
- Não parecer entrevista formal.
- Os dois devem ensinar.
- B não deve existir apenas para perguntar.
- A não deve monopolizar a conversa.
- Os dois podem explicar conceitos.
- Os dois podem trazer exemplos.
- Um pode questionar o outro.
- Um pode complementar o outro.
- Um pode corrigir ou esclarecer uma ideia.
- Pode haver analogias.
- Pode haver exemplos práticos.
- Use transições naturais.
- Evite exagero em expressões artificiais.
- Evite repetir o nome do outro apresentador.


TAMANHO DAS FALAS:

Faça aproximadamente entre 16 e 22 falas
nesta parte.

Cada fala pode ter normalmente entre
2 e 4 frases.

Evite falas extremamente longas.


PARA TEMAS DE CONCURSO OU PRF:

- Explique pensando em quem está estudando.
- Mostre pegadinhas comuns.
- Traga situações práticas.
- Explique como pode aparecer em questões.
- Quando fizer sentido, mencione Cebraspe.
- Não invente artigos de lei.
- Não invente jurisprudência.
- Não invente decisões judiciais.
- Não invente números ou regras específicas
  quando não tiver segurança.
- Se tiver dúvida sobre um detalhe jurídico,
  explique o conceito de forma geral.


CONTINUIDADE:

Este é um único episódio.

O ouvinte NÃO pode perceber que o conteúdo
foi gerado em três chamadas diferentes.

Não diga:
"parte 1",
"parte 2",
"parte 3",
"primeiro bloco",
"segundo bloco",
"terceiro bloco".

Faça tudo parecer uma conversa única.


FORMATO:

Retorne SOMENTE JSON válido.

Não escreva texto antes do JSON.

Não escreva texto depois do JSON.

Não use Markdown.

Formato:

{{
  "falas": [
    {{
      "speaker": "A",
      "text": "fala"
    }},
    {{
      "speaker": "B",
      "text": "fala"
    }}
  ]
}}
"""

        try:

            dados_resposta = chamar_gemini(
                prompt,
                schema,
                max_output_tokens=8192,
                temperature=0.78,
            )

            falas = extrair_falas(
                dados_resposta
            )

            print("")
            print(
                f"Parte {numero_parte} "
                f"gerada com sucesso."
            )

            print(
                f"Quantidade de falas: "
                f"{len(falas)}"
            )

            return falas

        except Exception as erro:

            ultimo_erro = erro

            print("")
            print(
                f"Falha ao gerar "
                f"parte {numero_parte}: "
                f"{erro}"
            )

            if tentativa < len(
                TENTATIVAS_PALAVRAS
            ):

                print("")
                print(
                    "Tentando novamente "
                    "com uma resposta menor..."
                )

    raise RuntimeError(
        f"Não foi possível gerar "
        f"a parte {numero_parte}."
    ) from ultimo_erro


# ==========================================================
# GERAR EPISÓDIO COMPLETO
# ==========================================================

def gerar_episodio_completo(
    tema
):

    plano = gerar_plano_episodio(
        tema
    )

    print("")
    print("=" * 70)

    print(
        "PLANEJAMENTO DO EPISÓDIO"
    )

    print("=" * 70)

    print("")
    print(
        "PARTE 1:"
    )

    print(
        plano["parte_1"]
    )

    print("")
    print(
        "PARTE 2:"
    )

    print(
        plano["parte_2"]
    )

    print("")
    print(
        "PARTE 3:"
    )

    print(
        plano["parte_3"]
    )

    falas_completas = []

    falas_por_parte = []

    for numero_parte in range(
        1,
        QUANTIDADE_PARTES + 1
    ):

        falas_parte = gerar_parte(
            tema=tema,
            numero_parte=numero_parte,
            plano=plano,
            falas_anteriores=falas_completas,
        )

        falas_por_parte.append(
            falas_parte
        )

        falas_completas.extend(
            falas_parte
        )

    print("")
    print("=" * 70)

    print(
        "EPISÓDIO COMPLETO GERADO"
    )

    print("=" * 70)

    print(
        f"Total de falas: "
        f"{len(falas_completas)}"
    )

    return (
        plano,
        falas_por_parte,
        falas_completas
    )


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
        "# Tema"
    )

    linhas.append("")

    linhas.append(
        tema
    )

    linhas.append("")

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
            f"## {nome}"
        )

        linhas.append("")

        linhas.append(
            texto
        )

        linhas.append("")

    caminho.write_text(
        "\n".join(linhas),
        encoding="utf-8",
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

    for tentativa in range(
        1,
        4
    ):

        try:

            comunicador = edge_tts.Communicate(
                texto,
                voz,
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
                f"Falha no edge-tts. "
                f"Tentativa {tentativa}/3: "
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
# GERAR TODAS AS FALAS EM ÁUDIO
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

        nome = NOMES_APRESENTADORES[
            speaker
        ]

        caminho = (
            pasta_temporaria
            / f"fala_{numero:03d}_{speaker}.mp3"
        )

        print(
            f"Gerando áudio "
            f"{numero}/{total} "
            f"- {nome}"
        )

        await gerar_fala_audio(
            texto,
            voz,
            caminho,
        )

        arquivos.append(
            caminho
        )

    return arquivos


# ==========================================================
# JUNTAR ÁUDIOS COM FFMPEG
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
        "\n".join(linhas),
        encoding="utf-8",
    )

    print("")
    print("=" * 70)

    print(
        "JUNTANDO TODAS AS FALAS"
    )

    print("=" * 70)

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
        str(arquivo_lista),

        "-vn",

        "-c:a",
        "libmp3lame",

        "-b:a",
        "128k",

        str(caminho_final),
    ]

    subprocess.run(
        comando,
        check=True,
    )

    if (
        not caminho_final.exists()
        or caminho_final.stat().st_size < 5000
    ):

        raise RuntimeError(
            "Podcast final não foi "
            "gerado corretamente."
        )

    tamanho_mb = (
        caminho_final.stat().st_size
        / 1024
        / 1024
    )

    print("")
    print(
        f"Podcast criado: "
        f"{caminho_final}"
    )

    print(
        f"Tamanho: "
        f"{tamanho_mb:.2f} MB"
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
        "👥 Dois apresentadores\n"
        "⏱️ Aproximadamente 20 minutos\n\n"
        f"*Tema {numero_tema}/{total_temas}:*\n"
        f"{tema}\n\n"
        f"🔗 {link_repo}"
    )

    print("")
    print("=" * 70)

    print(
        "ENVIANDO PARA O TELEGRAM"
    )

    print("=" * 70)

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

            timeout=300,
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
    print("=" * 70)

    print(
        "PODCAST AUTOMÁTICO "
        "- DOIS APRESENTADORES"
    )

    print(
        "GERAÇÃO EM 3 PARTES "
        "- APROXIMADAMENTE 20 MINUTOS"
    )

    print("=" * 70)

    print("")
    print(
        "Horário de Brasília:"
    )

    print(
        agora.strftime(
            "%d/%m/%Y %H:%M:%S"
        )
    )


    # ======================================================
    # SELECIONAR TEMA
    # ======================================================

    temas = carregar_temas()

    estado = carregar_estado()

    indice, tema = escolher_proximo_tema(
        temas,
        estado,
    )

    print("")
    print("=" * 70)

    print(
        f"TEMA SELECIONADO "
        f"{indice + 1}/{len(temas)}"
    )

    print("=" * 70)

    print("")
    print(
        tema
    )


    # ======================================================
    # CRIAR PASTA
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
        exist_ok=True,
    )

    print("")
    print(
        f"Pasta do episódio: "
        f"{pasta_episodio}"
    )


    # ======================================================
    # GERAR EPISÓDIO
    # ======================================================

    (
        plano,
        falas_por_parte,
        falas
    ) = gerar_episodio_completo(
        tema
    )


    # ======================================================
    # SALVAR PLANEJAMENTO
    # ======================================================

    caminho_plano = (
        pasta_episodio
        / "plano.json"
    )

    caminho_plano.write_text(

        json.dumps(
            plano,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )


    # ======================================================
    # SALVAR AS 3 PARTES
    # ======================================================

    for numero, falas_parte in enumerate(
        falas_por_parte,
        start=1
    ):

        caminho_parte = (
            pasta_episodio
            / f"parte_{numero}.json"
        )

        caminho_parte.write_text(

            json.dumps(
                {
                    "parte": numero,
                    "falas": falas_parte,
                },
                ensure_ascii=False,
                indent=2,
            ),

            encoding="utf-8",
        )


    # ======================================================
    # SALVAR DIÁLOGO COMPLETO
    # ======================================================

    caminho_dialogo = (
        pasta_episodio
        / "dialogo.json"
    )

    caminho_dialogo.write_text(

        json.dumps(
            {
                "tema": tema,
                "plano": plano,
                "falas": falas,
            },
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )


    # ======================================================
    # SALVAR ROTEIRO LEGÍVEL
    # ======================================================

    caminho_roteiro = (
        pasta_episodio
        / "roteiro.md"
    )

    salvar_roteiro(
        falas,
        tema,
        caminho_roteiro,
    )

    print("")
    print(
        f"Roteiro salvo em: "
        f"{caminho_roteiro}"
    )


    # ======================================================
    # SALVAR METADADOS
    # ======================================================

    quantidade_falas_partes = [
        len(parte)
        for parte in falas_por_parte
    ]

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

        "modelo_gemini":
            MODELO_GEMINI,

        "quantidade_partes":
            QUANTIDADE_PARTES,

        "palavras_por_parte":
            PALAVRAS_POR_PARTE,

        "palavras_totais_alvo":
            (
                PALAVRAS_POR_PARTE
                * QUANTIDADE_PARTES
            ),

        "duracao_aproximada":
            "18 a 22 minutos",

        "apresentador_a":
            VOZ_A,

        "apresentador_b":
            VOZ_B,

        "total_falas":
            len(falas),

        "falas_por_parte":
            quantidade_falas_partes,
    }

    caminho_info = (
        pasta_episodio
        / "episodio.json"
    )

    caminho_info.write_text(

        json.dumps(
            dados_episodio,
            ensure_ascii=False,
            indent=2,
        ),

        encoding="utf-8",
    )


    # ======================================================
    # GERAR ÁUDIO
    # ======================================================

    caminho_audio = (
        pasta_episodio
        / "podcast.mp3"
    )

    print("")
    print("=" * 70)

    print(
        "GERANDO VOZES DO PODCAST"
    )

    print("=" * 70)

    # Os MP3 individuais ficam somente
    # temporariamente.
    #
    # Apenas o podcast final vai para
    # a pasta episodes.

    with tempfile.TemporaryDirectory(
        prefix="podcast_falas_"
    ) as pasta_temp:

        pasta_temporaria = Path(
            pasta_temp
        )

        arquivos_segmentos = asyncio.run(

            gerar_segmentos(
                falas,
                pasta_temporaria,
            )
        )

        juntar_audios(
            arquivos_segmentos,
            caminho_audio,
            pasta_temporaria,
        )


    # ======================================================
    # LINK DO REPOSITÓRIO
    # ======================================================

    repo = os.environ.get(
        "GITHUB_REPOSITORY",
        "SEU_USUARIO/SEU_REPO"
    )

    link_repo = (
        f"https://github.com/"
        f"{repo}"
        f"/tree/main/"
        f"episodes/"
        f"{data}/"
        f"{horario}"
    )


    # ======================================================
    # TELEGRAM
    # ======================================================

    enviar_para_telegram(
        str(caminho_audio),
        tema,
        link_repo,
        indice + 1,
        len(temas),
    )


    # ======================================================
    # ATUALIZAR ESTADO
    #
    # SOMENTE DEPOIS DE O TELEGRAM
    # CONFIRMAR O ENVIO.
    # ======================================================

    salvar_estado(
        indice,
        tema,
        agora,
    )


    # ======================================================
    # FINAL
    # ======================================================

    print("")
    print("=" * 70)

    print(
        "PROCESSO CONCLUÍDO "
        "COM SUCESSO"
    )

    print("=" * 70)

    print("")
    print(
        f"Tema: {tema}"
    )

    print(
        f"Partes: "
        f"{QUANTIDADE_PARTES}"
    )

    print(
        f"Total de falas: "
        f"{len(falas)}"
    )
 
    print(
        "Duração estimada: "
        "18 a 22 minutos"
    )

    print("")


# ==========================================================
# INICIAR
# ==========================================================

if __name__ == "__main__":

    main()