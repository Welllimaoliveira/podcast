"""
PODCAST AUTOMÁTICO PRF
DOIS APRESENTADORES + TEORIA + 4 QUESTÕES DE PROVAS ANTERIORES

Fluxo:

1. Lê topics.json.
2. Lê podcast_state.json.
3. Escolhe o próximo tema.
4. Lê questoes_prf.json.
5. Lê questoes_state.json.
6. Seleciona 4 questões de provas anteriores da disciplina.
7. Gera duas partes teóricas com Gemini.
8. Cria uma terceira parte com:
   - 4 questões
   - tempo para o aluno pensar
   - gabarito oficial
   - explicações
9. edge-tts gera duas vozes.
10. FFmpeg junta tudo em um MP3.
11. Envia para o Telegram.
12. Somente depois do envio:
    - atualiza podcast_state.json
    - atualiza questoes_state.json

IMPORTANTE:

O Gemini NÃO decide o gabarito das questões.

O gabarito vem obrigatoriamente de:

questoes_prf.json
"""

import os
import json
import asyncio
import datetime
import shutil
import subprocess
import tempfile
import unicodedata

from pathlib import Path
from zoneinfo import ZoneInfo

import requests
import edge_tts


# ==========================================================
# CONFIGURAÇÕES
# ==========================================================

VOZ_A = "pt-BR-AntonioNeural"
VOZ_B = "pt-BR-FranciscaNeural"

MODELO_GEMINI = "gemini-flash-latest"

# Duas partes teóricas.
# A terceira parte será o desafio das questões.
QUANTIDADE_PARTES_TEORIA = 2

# Tamanho de cada parte teórica.
PALAVRAS_POR_PARTE = 1050

# Se o Gemini cortar uma resposta,
# tenta novamente com tamanhos menores.
TENTATIVAS_PALAVRAS = [
    1050,
    950,
    850,
]

# Número de questões por episódio.
QUESTOES_POR_EPISODIO = 4

# Número de falas anteriores passadas ao Gemini
# para manter continuidade entre parte 1 e 2.
FALAS_CONTEXTO = 8


# ==========================================================
# ARQUIVOS
# ==========================================================

ARQUIVO_TEMAS = Path(
    "topics.json"
)

ARQUIVO_ESTADO_PODCAST = Path(
    "podcast_state.json"
)

ARQUIVO_QUESTOES = Path(
    "questoes_prf.json"
)

ARQUIVO_ESTADO_QUESTOES = Path(
    "questoes_state.json"
)


# ==========================================================
# HORÁRIO
# ==========================================================

FUSO_BRASILIA = ZoneInfo(
    "America/Sao_Paulo"
)


# ==========================================================
# APRESENTADORES
# ==========================================================

NOMES_APRESENTADORES = {

    "A":
        "Apresentador 1",

    "B":
        "Apresentadora 2",
}


VOZES = {

    "A":
        VOZ_A,

    "B":
        VOZ_B,
}


# ==========================================================
# UTILIDADES
# ==========================================================

def normalizar_texto(
    texto
):

    texto = str(
        texto
    ).strip().lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(

        caractere

        for caractere in texto

        if unicodedata.category(
            caractere
        ) != "Mn"
    )

    return texto


# ==========================================================
# NORMALIZAR DISCIPLINA
# ==========================================================

def disciplina_canonica(
    texto
):

    texto = normalizar_texto(
        texto
    )

    if (
        "administrativo"
        in texto
    ):

        return "direito administrativo"

    if (
        "penal"
        in texto
    ):

        return "direito penal"

    if (
        "informat"
        in texto
    ):

        return "informatica"

    if (
        "portugues"
        in texto
    ):

        return "portugues"

    if (
        "transito"
        in texto
    ):

        return "transito"

    if (
        "ingles"
        in texto
    ):

        return "ingles"

    if (
        "racioc"
        in texto
        and
        "logic"
        in texto
    ):

        return "raciocinio logico"

    return texto


# ==========================================================
# DISCIPLINA DO TEMA
# ==========================================================

def disciplina_do_tema(
    tema
):

    return disciplina_canonica(
        tema
    )


# ==========================================================
# NORMALIZAR GABARITO
# ==========================================================

def normalizar_gabarito(
    valor
):

    valor = normalizar_texto(
        valor
    )

    if valor in (
        "c",
        "certo",
        "correto",
        "verdadeiro",
    ):

        return "CERTO"

    if valor in (
        "e",
        "errado",
        "incorreto",
        "falso",
    ):

        return "ERRADO"

    raise ValueError(
        f"Gabarito inválido: {valor}"
    )


# ==========================================================
# CARREGAR TEMAS
# ==========================================================

def carregar_temas():

    if not ARQUIVO_TEMAS.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: "
            f"{ARQUIVO_TEMAS}"
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
            "O campo 'temas' "
            "precisa ser uma lista."
        )

    temas = [

        str(
            tema
        ).strip()

        for tema in temas

        if str(
            tema
        ).strip()
    ]

    if not temas:

        raise ValueError(
            "Nenhum tema encontrado."
        )

    return temas


# ==========================================================
# CARREGAR ESTADO PODCAST
# ==========================================================

def carregar_estado_podcast():

    if not ARQUIVO_ESTADO_PODCAST.exists():

        return {

            "ultimo_indice":
                -1,

            "ultimo_tema":
                None,

            "ultima_execucao":
                None,
        }

    try:

        with ARQUIVO_ESTADO_PODCAST.open(
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
                "Estado inválido."
            )

        return estado

    except Exception as erro:

        print("")
        print(
            "AVISO:"
        )

        print(
            "Não foi possível carregar "
            "podcast_state.json."
        )

        print(
            erro
        )

        return {

            "ultimo_indice":
                -1,

            "ultimo_tema":
                None,

            "ultima_execucao":
                None,
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

            indice_anterior
            + 1

        ) % len(
            temas
        )

    else:

        indice = 0

    return (
        indice,
        temas[
            indice
        ]
    )


# ==========================================================
# SALVAR ESTADO PODCAST
# ==========================================================

def salvar_estado_podcast(
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

    with ARQUIVO_ESTADO_PODCAST.open(
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
        "Estado do podcast atualizado."
    )

    print(
        f"Último tema: {tema}"
    )


# ==========================================================
# CARREGAR QUESTÕES
# ==========================================================

def carregar_questoes():

    if not ARQUIVO_QUESTOES.exists():

        raise FileNotFoundError(
            f"Arquivo não encontrado: "
            f"{ARQUIVO_QUESTOES}"
        )

    with ARQUIVO_QUESTOES.open(
        "r",
        encoding="utf-8"
    ) as arquivo:

        dados = json.load(
            arquivo
        )

    # ------------------------------------------------------
    # Aceita duas estruturas:
    #
    # NOVA:
    #
    # {
    #   "questoes": [
    #       {...},
    #       {...}
    #   ]
    # }
    #
    # ANTIGA:
    #
    # {
    #   "id": "...",
    #   "questao": "...",
    #   ...
    # }
    #
    # Isso evita quebrar enquanto você
    # atualiza o JSON.
    # ------------------------------------------------------

    if (
        isinstance(
            dados,
            dict
        )
        and
        "questoes" in dados
    ):

        questoes = dados[
            "questoes"
        ]

    elif (
        isinstance(
            dados,
            list
        )
    ):

        questoes = dados

    elif (
        isinstance(
            dados,
            dict
        )
        and
        "id" in dados
    ):

        questoes = [
            dados
        ]

    else:

        raise ValueError(
            "Formato de questoes_prf.json "
            "não reconhecido."
        )

    questoes_validas = []

    ids_encontrados = set()

    for questao in questoes:

        if not isinstance(
            questao,
            dict
        ):

            continue

        id_questao = str(
            questao.get(
                "id",
                ""
            )
        ).strip()

        disciplina = str(
            questao.get(
                "disciplina",
                ""
            )
        ).strip()

        texto_questao = str(
            questao.get(
                "questao",
                ""
            )
        ).strip()

        gabarito_original = questao.get(
            "gabarito",
            ""
        )

        if not id_questao:

            continue

        if id_questao in ids_encontrados:

            raise ValueError(
                f"ID de questão repetido: "
                f"{id_questao}"
            )

        if not disciplina:

            continue

        if not texto_questao:

            continue

        try:

            gabarito = normalizar_gabarito(
                gabarito_original
            )

        except Exception:

            print(
                f"Questão ignorada "
                f"por gabarito inválido: "
                f"{id_questao}"
            )

            continue

        questao_tratada = {

            "id":
                id_questao,

            "ano":
                questao.get(
                    "ano",
                    ""
                ),

            "banca":
                str(
                    questao.get(
                        "banca",
                        "CEBRASPE"
                    )
                ).strip(),

            "disciplina":
                disciplina,

            "disciplina_canonica":
                disciplina_canonica(
                    disciplina
                ),

            "item_original":
                questao.get(
                    "item_original",
                    ""
                ),

            "questao":
                texto_questao,

            "gabarito":
                gabarito,

            "fonte":
                str(
                    questao.get(
                        "fonte",
                        ""
                    )
                ).strip(),
        }

        ids_encontrados.add(
            id_questao
        )

        questoes_validas.append(
            questao_tratada
        )

    if not questoes_validas:

        raise RuntimeError(
            "Nenhuma questão válida foi "
            "encontrada em questoes_prf.json."
        )

    return questoes_validas


# ==========================================================
# CARREGAR ESTADO DAS QUESTÕES
# ==========================================================

def carregar_estado_questoes():

    if not ARQUIVO_ESTADO_QUESTOES.exists():

        return {

            "questoes_usadas":
                []
        }

    try:

        with ARQUIVO_ESTADO_QUESTOES.open(
            "r",
            encoding="utf-8"
        ) as arquivo:

            estado = json.load(
                arquivo
            )

        usados = estado.get(
            "questoes_usadas",
            []
        )

        if not isinstance(
            usados,
            list
        ):

            usados = []

        estado[
            "questoes_usadas"
        ] = [

            str(
                item
            ).strip()

            for item in usados
        ]

        return estado

    except Exception as erro:

        print("")
        print(
            "AVISO:"
        )

        print(
            "Não foi possível carregar "
            "questoes_state.json."
        )

        print(
            erro
        )

        return {

            "questoes_usadas":
                []
        }


# ==========================================================
# SELECIONAR 4 QUESTÕES
# ==========================================================

def selecionar_questoes(
    tema,
    questoes,
    estado_questoes
):

    disciplina = disciplina_do_tema(
        tema
    )

    candidatas = [

        questao

        for questao in questoes

        if questao[
            "disciplina_canonica"
        ] == disciplina
    ]

    # ------------------------------------------------------
    # Precisa haver pelo menos 4 questões
    # cadastradas para a disciplina.
    # ------------------------------------------------------

    if len(
        candidatas
    ) < QUESTOES_POR_EPISODIO:

        raise RuntimeError(

            f"Não existem questões suficientes "
            f"para a disciplina '{disciplina}'.\n"
            f"Encontradas: {len(candidatas)}\n"
            f"Necessárias: "
            f"{QUESTOES_POR_EPISODIO}\n\n"
            f"Adicione mais questões reais "
            f"em questoes_prf.json."
        )

    usados = estado_questoes.get(
        "questoes_usadas",
        []
    )

    usados_set = set(
        usados
    )

    disponiveis = [

        questao

        for questao in candidatas

        if questao[
            "id"
        ] not in usados_set
    ]

    # ------------------------------------------------------
    # CASO 1:
    #
    # Ainda existem 4 ou mais inéditas.
    # ------------------------------------------------------

    if len(
        disponiveis
    ) >= QUESTOES_POR_EPISODIO:

        selecionadas = disponiveis[
            :QUESTOES_POR_EPISODIO
        ]

        controle = {

            "reiniciou_ciclo":
                False,

            "ids_disciplina":
                [
                    q["id"]
                    for q in candidatas
                ],

            "ids_novo_ciclo":
                [],
        }

        return (
            disciplina,
            selecionadas,
            controle
        )

    # ------------------------------------------------------
    # CASO 2:
    #
    # Restaram 1, 2 ou 3 questões inéditas.
    #
    # Primeiro usamos todas elas.
    #
    # Depois iniciamos novo ciclo para completar
    # as 4 do episódio.
    #
    # Assim nenhuma questão fica esquecida.
    # ------------------------------------------------------

    selecionadas = list(
        disponiveis
    )

    faltam = (
        QUESTOES_POR_EPISODIO
        - len(
            selecionadas
        )
    )

    ids_selecionados = {

        questao[
            "id"
        ]

        for questao in selecionadas
    }

    reciclaveis = [

        questao

        for questao in candidatas

        if questao[
            "id"
        ] not in ids_selecionados
    ]

    inicio_novo_ciclo = reciclaveis[
        :faltam
    ]

    selecionadas.extend(
        inicio_novo_ciclo
    )

    controle = {

        "reiniciou_ciclo":
            True,

        "ids_disciplina":
            [
                q["id"]
                for q in candidatas
            ],

        "ids_novo_ciclo":
            [
                q["id"]
                for q in inicio_novo_ciclo
            ],
    }

    return (
        disciplina,
        selecionadas,
        controle
    )


# ==========================================================
# SALVAR ESTADO DAS QUESTÕES
# ==========================================================

def salvar_estado_questoes(
    estado_anterior,
    selecionadas,
    controle,
    disciplina,
    agora
):

    usados_anteriores = estado_anterior.get(
        "questoes_usadas",
        []
    )

    ids_selecionadas = [

        questao[
            "id"
        ]

        for questao in selecionadas
    ]

    # ------------------------------------------------------
    # CICLO NORMAL
    # ------------------------------------------------------

    if not controle[
        "reiniciou_ciclo"
    ]:

        novos_usados = list(
            usados_anteriores
        )

        for id_questao in ids_selecionadas:

            if id_questao not in novos_usados:

                novos_usados.append(
                    id_questao
                )

    # ------------------------------------------------------
    # NOVO CICLO
    #
    # Quando esgotamos a disciplina:
    #
    # removemos do controle os IDs antigos
    # daquela disciplina.
    #
    # Mantemos IDs de outras disciplinas.
    #
    # Depois registramos as primeiras questões
    # que já entraram no novo ciclo.
    # ------------------------------------------------------

    else:

        ids_disciplina = set(
            controle[
                "ids_disciplina"
            ]
        )

        novos_usados = [

            id_questao

            for id_questao in usados_anteriores

            if id_questao not in ids_disciplina
        ]

        for id_questao in controle[
            "ids_novo_ciclo"
        ]:

            if id_questao not in novos_usados:

                novos_usados.append(
                    id_questao
                )

    estado = {

        "questoes_usadas":
            novos_usados,

        "ultima_disciplina":
            disciplina,

        "ultimas_questoes":
            ids_selecionadas,

        "ultima_execucao":
            agora.isoformat(),
    }

    with ARQUIVO_ESTADO_QUESTOES.open(
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
        "Controle das questões atualizado."
    )

    print(
        "Questões utilizadas:"
    )

    for id_questao in ids_selecionadas:

        print(
            f" - {id_questao}"
        )


# ==========================================================
# LIMPAR JSON GEMINI
# ==========================================================

def limpar_json_gemini(
    texto
):

    texto = str(
        texto
    ).strip()

    if texto.startswith(
        "```"
    ):

        linhas = texto.splitlines()

        if (
            linhas
            and
            linhas[0].startswith(
                "```"
            )
        ):

            linhas = linhas[
                1:
            ]

        if (
            linhas
            and
            linhas[-1].strip() == "```"
        ):

            linhas = linhas[
                :-1
            ]

        texto = "\n".join(
            linhas
        )

    return texto.strip()


# ==========================================================
# CHAMAR GEMINI
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
                        "text":
                            prompt
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
# OBTER TEXTO GEMINI
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

    candidato = candidatos[
        0
    ]

    finish_reason = candidato.get(
        "finishReason",
        "DESCONHECIDO"
    )

    print(
        f"Finish reason: "
        f"{finish_reason}"
    )

    if finish_reason == "MAX_TOKENS":

        raise RuntimeError(
            "MAX_TOKENS"
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

    texto = partes[
        0
    ].get(
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
# SCHEMA DE FALAS
# ==========================================================

def schema_falas():

    return {

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
            },
        },

        "required": [

            "falas"
        ],
    }


# ==========================================================
# EXTRAIR FALAS
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
            texto[
                -600:
            ]
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
            "O campo 'falas' "
            "não é uma lista."
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

                "speaker":
                    speaker,

                "text":
                    texto_fala,
            }
        )

    if len(
        falas_validas
    ) < 8:

        raise RuntimeError(

            f"Poucas falas válidas: "
            f"{len(falas_validas)}"
        )

    return falas_validas


# ==========================================================
# PLANEJAMENTO DO EPISÓDIO
# ==========================================================

def gerar_plano_episodio(
    tema
):

    print("")
    print(
        "=" * 70
    )

    print(
        "CRIANDO PLANEJAMENTO "
        "DO EPISÓDIO"
    )

    print(
        "=" * 70
    )

    prompt = f"""
Crie um planejamento para as DUAS PARTES
TEÓRICAS de um podcast educacional.

Tema:

"{tema}"

Depois dessas duas partes haverá uma terceira
parte contendo quatro questões reais de provas
anteriores da PRF.

Portanto:

PARTE 1:
Introdução natural, fundamentos, contexto
e conceitos essenciais.

PARTE 2:
Aprofundamento, aplicações, exemplos,
comparações e pegadinhas de prova.

NÃO coloque questões específicas de provas
anteriores nessas duas partes.

A parte de questões será criada separadamente.

Quando o assunto for relacionado à legislação:

- não invente artigos;
- não invente jurisprudência;
- não invente decisões;
- se não tiver segurança sobre um número
  específico, explique apenas o conceito.

Retorne somente JSON.
"""

    schema = {

        "type":
            "OBJECT",

        "properties": {

            "parte_1": {

                "type":
                    "STRING",
            },

            "parte_2": {

                "type":
                    "STRING",
            },
        },

        "required": [

            "parte_1",

            "parte_2",
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
            plano.get(
                "parte_1"
            )
            and
            plano.get(
                "parte_2"
            )
        ):

            print("")
            print(
                "Planejamento criado."
            )

            return plano

    except Exception as erro:

        print("")
        print(
            "Falha no planejamento "
            "automático."
        )

        print(
            erro
        )

    return {

        "parte_1":
            (
                "Apresentar o assunto, "
                "contextualizar sua importância "
                "e explicar os fundamentos."
            ),

        "parte_2":
            (
                "Aprofundar o assunto, trazer "
                "exemplos, aplicações e pegadinhas "
                "frequentes de prova."
            ),
    }


# ==========================================================
# CONTEXTO DA CONVERSA
# ==========================================================

def montar_contexto_continuidade(
    falas
):

    if not falas:

        return (
            "Não existe conversa anterior."
        )

    ultimas = falas[
        -FALAS_CONTEXTO:
    ]

    linhas = []

    for fala in ultimas:

        linhas.append(

            f"{fala['speaker']}: "
            f"{fala['text']}"
        )

    return "\n".join(
        linhas
    )


# ==========================================================
# GERAR PARTE TEÓRICA
# ==========================================================

def gerar_parte_teorica(
    tema,
    numero_parte,
    plano,
    falas_anteriores
):

    contexto = montar_contexto_continuidade(
        falas_anteriores
    )

    objetivo = plano[
        f"parte_{numero_parte}"
    ]

    if numero_parte == 1:

        instrucao = """
Esta é a primeira parte.

A deve iniciar.

Faça uma abertura envolvente.

Não diga:
"Bem-vindos ao podcast".

No final não faça despedida.
"""

    else:

        instrucao = """
Esta é a continuação direta da conversa.

Não faça uma nova abertura.

Não diga:
"segunda parte",
"novo bloco",
"voltando ao podcast".

Não repita o que já foi explicado.

No final faça uma transição natural indicando
que agora será hora de testar o conhecimento
com algumas questões.
"""

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
            f"GERANDO PARTE TEÓRICA "
            f"{numero_parte}/2"
        )

        print(
            f"Tentativa "
            f"{tentativa}/"
            f"{len(TENTATIVAS_PALAVRAS)}"
        )

        print(
            f"Alvo: "
            f"{palavras} palavras"
        )

        print(
            "=" * 70
        )

        prompt = f"""
Crie uma conversa natural entre dois
apresentadores brasileiros.

TEMA:

"{tema}"


OBJETIVO DESTA PARTE:

{objetivo}


CONTEXTO DA CONVERSA ANTERIOR:

{contexto}


{instrucao}


TAMANHO:

Aproximadamente {palavras} palavras.


PERSONAGENS:

A = apresentador masculino.

B = apresentadora feminina.


ESTILO:

- conversa natural;
- linguagem didática;
- os dois devem ensinar;
- B não deve apenas perguntar;
- A não deve monopolizar;
- use exemplos práticos;
- use comparações;
- use pegadinhas de concurso quando pertinente;
- mencione Cebraspe quando fizer sentido;
- evite exagero em reações artificiais;
- não invente legislação;
- não invente jurisprudência;
- não invente números quando não tiver segurança.


FALAS:

Crie aproximadamente entre 16 e 22 falas.

Cada fala pode ter entre 2 e 4 frases.

O ouvinte não deve perceber divisão artificial
entre os blocos.

Retorne somente JSON no formato:

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

            dados = chamar_gemini(

                prompt,

                schema_falas(),

                max_output_tokens=8192,

                temperature=0.78,
            )

            falas = extrair_falas(
                dados
            )

            print("")
            print(
                f"Parte {numero_parte} "
                f"gerada."
            )

            print(
                f"Falas: "
                f"{len(falas)}"
            )

            return falas

        except Exception as erro:

            ultimo_erro = erro

            print("")
            print(
                f"Falha: {erro}"
            )

            if tentativa < len(
                TENTATIVAS_PALAVRAS
            ):

                print(
                    "Tentando novamente "
                    "com texto menor..."
                )

    raise RuntimeError(

        f"Não foi possível gerar "
        f"a parte teórica "
        f"{numero_parte}."

    ) from ultimo_erro


# ==========================================================
# GERAR EXPLICAÇÕES DAS QUESTÕES
# ==========================================================

def gerar_explicacoes_questoes(
    tema,
    questoes
):

    print("")
    print(
        "=" * 70
    )

    print(
        "GERANDO EXPLICAÇÕES "
        "DAS 4 QUESTÕES"
    )

    print(
        "=" * 70
    )

    blocos = []

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        blocos.append(

            f"""
QUESTÃO {numero}

ID:
{questao["id"]}

ANO:
{questao["ano"]}

BANCA:
{questao["banca"]}

DISCIPLINA:
{questao["disciplina"]}

ITEM ORIGINAL:
{questao["item_original"]}

QUESTÃO:
{questao["questao"]}

GABARITO OFICIAL:
{questao["gabarito"]}
"""
        )

    texto_questoes = "\n".join(
        blocos
    )

    prompt = f"""
Você está preparando a correção didática
de quatro questões de provas anteriores
da PRF.

Tema atual:

"{tema}"


QUESTÕES E GABARITOS OFICIAIS:

{texto_questoes}


REGRA MAIS IMPORTANTE:

O campo GABARITO OFICIAL é FIXO.

Você NÃO pode:

- mudar o gabarito;
- corrigir o gabarito;
- substituir o gabarito;
- dizer que deveria ser outro;
- inventar outro resultado.

Sua função é SOMENTE explicar didaticamente
o raciocínio correspondente ao gabarito
oficial informado.


Para cada questão:

- explique de forma clara;
- explique a pegadinha;
- mostre o raciocínio que o candidato
  deveria utilizar;
- mantenha a explicação relativamente curta;
- use aproximadamente 100 a 160 palavras;
- não invente legislação;
- não invente jurisprudência;
- não invente números;
- considere que a questão pertence à prova
  e ao ano indicados;
- caso uma norma possa ter mudado desde
  a prova, não trate automaticamente
  aquela regra antiga como situação atual.


Retorne somente JSON.

Formato:

{{
  "explicacoes": [
    {{
      "id": "ID_DA_QUESTAO",
      "explicacao": "explicação"
    }}
  ]
}}
"""

    schema = {

        "type":
            "OBJECT",

        "properties": {

            "explicacoes": {

                "type":
                    "ARRAY",

                "items": {

                    "type":
                        "OBJECT",

                    "properties": {

                        "id": {

                            "type":
                                "STRING",
                        },

                        "explicacao": {

                            "type":
                                "STRING",
                        },
                    },

                    "required": [

                        "id",

                        "explicacao",
                    ],
                },
            },
        },

        "required": [

            "explicacoes"
        ],
    }

    ultimo_erro = None

    for tentativa in range(
        1,
        4
    ):

        try:

            print("")
            print(
                f"Tentativa "
                f"{tentativa}/3"
            )

            dados = chamar_gemini(

                prompt,

                schema,

                max_output_tokens=5000,

                temperature=0.45,
            )

            texto = obter_texto_gemini(
                dados
            )

            resposta = json.loads(
                texto
            )

            explicacoes_recebidas = resposta.get(
                "explicacoes",
                []
            )

            mapa = {}

            for item in explicacoes_recebidas:

                if not isinstance(
                    item,
                    dict
                ):

                    continue

                id_questao = str(
                    item.get(
                        "id",
                        ""
                    )
                ).strip()

                explicacao = str(
                    item.get(
                        "explicacao",
                        ""
                    )
                ).strip()

                if (
                    id_questao
                    and
                    explicacao
                ):

                    mapa[
                        id_questao
                    ] = explicacao

            faltando = [

                questao[
                    "id"
                ]

                for questao in questoes

                if questao[
                    "id"
                ] not in mapa
            ]

            if faltando:

                raise RuntimeError(

                    "Explicações ausentes "
                    "para: "
                    + ", ".join(
                        faltando
                    )
                )

            print("")
            print(
                "Explicações geradas."
            )

            return mapa

        except Exception as erro:

            ultimo_erro = erro

            print("")
            print(
                f"Falha: {erro}"
            )

    raise RuntimeError(

        "Não foi possível gerar "
        "as explicações das questões."

    ) from ultimo_erro


# ==========================================================
# MONTAR DESAFIO
# ==========================================================

def montar_falas_desafio(
    questoes,
    explicacoes
):

    falas = []

    # ------------------------------------------------------
    # INTRODUÇÃO
    # ------------------------------------------------------

    falas.append(

        {

            "speaker":
                "A",

            "text":
                (
                    "Agora chegou a hora de testar "
                    "de verdade o que você sabe. "
                    "Separei quatro questões de "
                    "provas anteriores da Polícia "
                    "Rodoviária Federal."
                )
        }
    )

    falas.append(

        {

            "speaker":
                "B",

            "text":
                (
                    "A regra é simples: escute as quatro "
                    "questões e marque mentalmente certo "
                    "ou errado. Não vamos revelar as "
                    "respostas agora. Depois das quatro, "
                    "a gente volta com o gabarito oficial "
                    "e explica cada uma."
                )
        }
    )

    falas.append(

        {

            "speaker":
                "A",

            "text":
                (
                    "Como estamos usando provas anteriores, "
                    "considere sempre o ano indicado e o "
                    "gabarito oficial daquela prova. "
                    "Legislação pode sofrer alterações "
                    "ao longo do tempo."
                )
        }
    )

    # ------------------------------------------------------
    # LER AS 4 QUESTÕES SEM RESPOSTA
    # ------------------------------------------------------

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        speaker = (
            "B"
            if numero % 2 == 1
            else "A"
        )

        ano = questao.get(
            "ano",
            ""
        )

        banca = questao.get(
            "banca",
            "CEBRASPE"
        )

        item_original = questao.get(
            "item_original",
            ""
        )

        referencia = (
            f"Questão {numero}. "
            f"PRF {ano}, "
            f"{banca}"
        )

        if item_original:

            referencia += (
                f", item "
                f"{item_original}"
            )

        referencia += ". "

        texto = (

            referencia

            + questao[
                "questao"
            ]

            + " Certo ou errado?"
        )

        falas.append(

            {

                "speaker":
                    speaker,

                "text":
                    texto,
            }
        )

        outro_speaker = (
            "A"
            if speaker == "B"
            else "B"
        )

        if numero < len(
            questoes
        ):

            falas.append(

                {

                    "speaker":
                        outro_speaker,

                    "text":
                        (
                            "Guarde sua resposta "
                            "e vamos para a próxima."
                        )
                }
            )

    # ------------------------------------------------------
    # MOMENTO PARA PENSAR
    # ------------------------------------------------------

    falas.append(

        {

            "speaker":
                "A",

            "text":
                (
                    "As quatro foram apresentadas. "
                    "Se você quiser mais tempo para "
                    "resolver, pause o áudio agora. "
                    "Quando estiver pronto, continue "
                    "para conferir o gabarito."
                )
        }
    )

    falas.append(

        {

            "speaker":
                "B",

            "text":
                (
                    "Vamos corrigir. Mais importante "
                    "do que acertar é entender exatamente "
                    "por que cada item está certo ou errado."
                )
        }
    )

    # ------------------------------------------------------
    # GABARITO + EXPLICAÇÃO
    # ------------------------------------------------------

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        speaker_gabarito = (
            "A"
            if numero % 2 == 1
            else "B"
        )

        speaker_explicacao = (
            "B"
            if speaker_gabarito == "A"
            else "A"
        )

        gabarito = questao[
            "gabarito"
        ]

        falas.append(

            {

                "speaker":
                    speaker_gabarito,

                "text":
                    (
                        f"Questão {numero}. "
                        f"O gabarito oficial é "
                        f"{gabarito}."
                    )
            }
        )

        explicacao = explicacoes.get(
            questao[
                "id"
            ],
            ""
        )

        falas.append(

            {

                "speaker":
                    speaker_explicacao,

                "text":
                    explicacao,
            }
        )

    # ------------------------------------------------------
    # ENCERRAMENTO
    # ------------------------------------------------------

    falas.append(

        {

            "speaker":
                "A",

            "text":
                (
                    "Se você errou alguma delas, "
                    "essa é justamente a questão "
                    "que merece entrar na sua lista "
                    "de revisão."
                )
        }
    )

    falas.append(

        {

            "speaker":
                "B",

            "text":
                (
                    "E se acertou as quatro, ótimo. "
                    "Mas não fique apenas no acerto: "
                    "tenha certeza de que você consegue "
                    "explicar o motivo de cada resposta."
                )
        }
    )

    falas.append(

        {

            "speaker":
                "A",

            "text":
                (
                    "Continuamos no próximo episódio "
                    "com outro tema e quatro novas "
                    "questões. Bons estudos e até lá."
                )
        }
    )

    return falas


# ==========================================================
# GERAR EPISÓDIO COMPLETO
# ==========================================================

def gerar_episodio_completo(
    tema,
    questoes
):

    plano = gerar_plano_episodio(
        tema
    )

    print("")
    print(
        "=" * 70
    )

    print(
        "PLANEJAMENTO"
    )

    print(
        "=" * 70
    )

    print("")
    print(
        "PARTE 1:"
    )

    print(
        plano[
            "parte_1"
        ]
    )

    print("")
    print(
        "PARTE 2:"
    )

    print(
        plano[
            "parte_2"
        ]
    )

    falas_completas = []

    falas_partes = []

    # ------------------------------------------------------
    # PARTE 1
    # ------------------------------------------------------

    parte_1 = gerar_parte_teorica(

        tema,

        1,

        plano,

        falas_completas
    )

    falas_partes.append(
        parte_1
    )

    falas_completas.extend(
        parte_1
    )

    # ------------------------------------------------------
    # PARTE 2
    # ------------------------------------------------------

    parte_2 = gerar_parte_teorica(

        tema,

        2,

        plano,

        falas_completas
    )

    falas_partes.append(
        parte_2
    )

    falas_completas.extend(
        parte_2
    )

    # ------------------------------------------------------
    # QUESTÕES
    # ------------------------------------------------------

    explicacoes = gerar_explicacoes_questoes(

        tema,

        questoes
    )

    parte_3 = montar_falas_desafio(

        questoes,

        explicacoes
    )

    falas_partes.append(
        parte_3
    )

    falas_completas.extend(
        parte_3
    )

    print("")
    print(
        "=" * 70
    )

    print(
        "EPISÓDIO COMPLETO GERADO"
    )

    print(
        "=" * 70
    )

    print(
        f"Total de falas: "
        f"{len(falas_completas)}"
    )

    return (

        plano,

        falas_partes,

        falas_completas,

        explicacoes
    )


# ==========================================================
# SALVAR ROTEIRO
# ==========================================================

def salvar_roteiro(
    falas,
    tema,
    caminho
):

    linhas = [

        "# Tema",

        "",

        tema,

        "",
    ]

    for fala in falas:

        nome = NOMES_APRESENTADORES[
            fala[
                "speaker"
            ]
        ]

        linhas.append(
            f"## {nome}"
        )

        linhas.append(
            ""
        )

        linhas.append(
            fala[
                "text"
            ]
        )

        linhas.append(
            ""
        )

    caminho.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8",
    )


# ==========================================================
# SALVAR DESAFIO EM TEXTO
# ==========================================================

def salvar_desafio_questoes(
    questoes,
    explicacoes,
    caminho
):

    linhas = []

    linhas.append(
        "# DESAFIO PRF"
    )

    linhas.append(
        ""
    )

    linhas.append(
        "Resolva as quatro questões antes "
        "de olhar o gabarito."
    )

    linhas.append(
        ""
    )

    # ------------------------------------------------------
    # QUESTÕES
    # ------------------------------------------------------

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        linhas.append(
            f"## Questão {numero}"
        )

        linhas.append(
            ""
        )

        linhas.append(

            f"PRF {questao['ano']} - "
            f"{questao['banca']} - "
            f"Item {questao['item_original']}"
        )

        linhas.append(
            ""
        )

        linhas.append(
            questao[
                "questao"
            ]
        )

        linhas.append(
            ""
        )

        linhas.append(
            "**Certo ou Errado?**"
        )

        linhas.append(
            ""
        )

    # ------------------------------------------------------
    # GABARITO
    # ------------------------------------------------------

    linhas.append(
        "---"
    )

    linhas.append(
        ""
    )

    linhas.append(
        "# GABARITO"
    )

    linhas.append(
        ""
    )

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        linhas.append(

            f"{numero}. "
            f"{questao['gabarito']}"
        )

    # ------------------------------------------------------
    # EXPLICAÇÕES
    # ------------------------------------------------------

    linhas.append(
        ""
    )

    linhas.append(
        "# EXPLICAÇÕES"
    )

    linhas.append(
        ""
    )

    for numero, questao in enumerate(
        questoes,
        start=1
    ):

        linhas.append(
            f"## Questão {numero}"
        )

        linhas.append(
            ""
        )

        linhas.append(

            f"Gabarito oficial: "
            f"**{questao['gabarito']}**"
        )

        linhas.append(
            ""
        )

        linhas.append(

            explicacoes.get(
                questao[
                    "id"
                ],
                ""
            )
        )

        linhas.append(
            ""
        )

    caminho.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8",
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
                "Áudio vazio ou muito pequeno."
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

            caminho
        )

        arquivos.append(
            caminho
        )

    return arquivos


# ==========================================================
# JUNTAR ÁUDIOS
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
            "FFmpeg não encontrado."
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

            f"file "
            f"'{caminho_absoluto}'"
        )

    arquivo_lista.write_text(

        "\n".join(
            linhas
        ),

        encoding="utf-8",
    )

    print("")
    print(
        "=" * 70
    )

    print(
        "JUNTANDO TODAS AS FALAS"
    )

    print(
        "=" * 70
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

        check=True,
    )

    if (
        not caminho_final.exists()
        or
        caminho_final.stat().st_size < 5000
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

        "🎙️ Podcast de Estudos PRF\n\n"

        "👥 Dois apresentadores\n"

        "📝 4 questões de provas anteriores\n\n"

        f"*Tema {numero_tema}/"
        f"{total_temas}:*\n"

        f"{tema}\n\n"

        f"🔗 {link_repo}"
    )

    print("")
    print(
        "=" * 70
    )

    print(
        "ENVIANDO PARA TELEGRAM"
    )

    print(
        "=" * 70
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
        "Podcast enviado ao Telegram."
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
        "PODCAST AUTOMÁTICO PRF"
    )

    print(
        "TEORIA + 4 QUESTÕES "
        "DE PROVAS ANTERIORES"
    )

    print(
        "=" * 70
    )

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
    # TEMA
    # ======================================================

    temas = carregar_temas()

    estado_podcast = carregar_estado_podcast()

    indice, tema = escolher_proximo_tema(

        temas,

        estado_podcast
    )

    print("")
    print(
        "=" * 70
    )

    print(

        f"TEMA "
        f"{indice + 1}/"
        f"{len(temas)}"
    )

    print(
        "=" * 70
    )

    print("")
    print(
        tema
    )


    # ======================================================
    # QUESTÕES
    # ======================================================

    questoes_banco = carregar_questoes()

    estado_questoes = carregar_estado_questoes()

    (
        disciplina,
        questoes_selecionadas,
        controle_questoes
    ) = selecionar_questoes(

        tema,

        questoes_banco,

        estado_questoes
    )

    print("")
    print(
        "=" * 70
    )

    print(
        "QUESTÕES SELECIONADAS"
    )

    print(
        "=" * 70
    )

    print("")
    print(
        f"Disciplina: "
        f"{disciplina}"
    )

    for numero, questao in enumerate(

        questoes_selecionadas,

        start=1

    ):

        print(

            f"{numero}. "
            f"{questao['id']} "
            f"- PRF "
            f"{questao['ano']} "
            f"- "
            f"{questao['gabarito']}"
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

        exist_ok=True,
    )

    print("")
    print(

        f"Pasta: "
        f"{pasta_episodio}"
    )


    # ======================================================
    # GERAR CONTEÚDO
    # ======================================================

    (
        plano,
        falas_partes,
        falas,
        explicacoes
    ) = gerar_episodio_completo(

        tema,

        questoes_selecionadas
    )


    # ======================================================
    # SALVAR PLANO
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

    for numero, parte in enumerate(

        falas_partes,

        start=1

    ):

        caminho_parte = (

            pasta_episodio

            / f"parte_{numero}.json"
        )

        caminho_parte.write_text(

            json.dumps(

                {

                    "parte":
                        numero,

                    "falas":
                        parte,
                },

                ensure_ascii=False,

                indent=2,
            ),

            encoding="utf-8",
        )


    # ======================================================
    # SALVAR QUESTÕES UTILIZADAS
    # ======================================================

    caminho_questoes = (

        pasta_episodio

        / "questoes_utilizadas.json"
    )

    caminho_questoes.write_text(

        json.dumps(

            {

                "disciplina":
                    disciplina,

                "questoes":
                    questoes_selecionadas,
            },

            ensure_ascii=False,

            indent=2,
        ),

        encoding="utf-8",
    )


    # ======================================================
    # SALVAR DESAFIO EM MARKDOWN
    # ======================================================

    caminho_desafio = (

        pasta_episodio

        / "desafio_questoes.md"
    )

    salvar_desafio_questoes(

        questoes_selecionadas,

        explicacoes,

        caminho_desafio
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

                "tema":
                    tema,

                "disciplina":
                    disciplina,

                "plano":
                    plano,

                "questoes":
                    questoes_selecionadas,

                "falas":
                    falas,
            },

            ensure_ascii=False,

            indent=2,
        ),

        encoding="utf-8",
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

        "disciplina":
            disciplina,

        "modelo_gemini":
            MODELO_GEMINI,

        "partes_teoricas":
            2,

        "parte_3":
            "Desafio com 4 questões",

        "quantidade_questoes":
            len(
                questoes_selecionadas
            ),

        "ids_questoes":
            [

                questao[
                    "id"
                ]

                for questao
                in questoes_selecionadas
            ],

        "apresentador_a":
            VOZ_A,

        "apresentador_b":
            VOZ_B,

        "total_falas":
            len(
                falas
            ),
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
    print(
        "=" * 70
    )

    print(
        "GERANDO ÁUDIO"
    )

    print(
        "=" * 70
    )

    with tempfile.TemporaryDirectory(

        prefix="podcast_falas_"

    ) as pasta_temp:

        pasta_temporaria = Path(
            pasta_temp
        )

        segmentos = asyncio.run(

            gerar_segmentos(

                falas,

                pasta_temporaria
            )
        )

        juntar_audios(

            segmentos,

            caminho_audio,

            pasta_temporaria
        )


    # ======================================================
    # LINK GITHUB
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
    # IMPORTANTE
    #
    # SÓ ATUALIZA OS ESTADOS DEPOIS
    # DE O TELEGRAM CONFIRMAR O ENVIO.
    # ======================================================

    salvar_estado_questoes(

        estado_questoes,

        questoes_selecionadas,

        controle_questoes,

        disciplina,

        agora
    )

    salvar_estado_podcast(

        indice,

        tema,

        agora
    )


    # ======================================================
    # FINAL
    # ======================================================

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
    print(
        f"Tema: {tema}"
    )

    print(
        f"Disciplina: "
        f"{disciplina}"
    )

    print(
        f"Questões: "
        f"{len(questoes_selecionadas)}"
    )

    print(
        f"Falas: "
        f"{len(falas)}"
    )

    print("")


# ==========================================================
# INICIAR
# ==========================================================

if __name__ == "__main__":

    main()