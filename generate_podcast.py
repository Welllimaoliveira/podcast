"""
Gerador diário de podcast:
1. Escolhe um tema do dia (topics.json, cíclico por dia do ano)
2. Gera um roteiro de ~5 minutos com a API do Google Gemini (tier gratuito)
3. Converte o roteiro em áudio (mp3) usando edge-tts (gratuito)
4. Salva os arquivos em episodes/AAAA-MM-DD/
5. Envia o áudio para o grupo do Telegram

Variáveis de ambiente necessárias (configuradas como Secrets no GitHub):
- GEMINI_API_KEY
- TELEGRAM_BOT_TOKEN
- TELEGRAM_CHAT_ID
- GITHUB_REPOSITORY (já vem automaticamente no GitHub Actions)
"""

import os
import json
import asyncio
import datetime
from pathlib import Path

import requests
import edge_tts

# ---------- Configurações ----------
VOZ = "pt-BR-AntonioNeural"        # voz masculina PT-BR. Alternativa: pt-BR-FranciscaNeural (feminina)
PALAVRAS_ALVO = 1500                # ~5 minutos de fala
# Modelo gratuito do Gemini. Se parar de funcionar, confira o modelo atual do tier
# gratuito em https://ai.google.dev/gemini-api/docs/pricing e troque aqui.
MODELO_GEMINI = "gemini-flash-latest"


def escolher_tema_do_dia() -> str:
    with open("topics.json", "r", encoding="utf-8") as f:
        dados = json.load(f)
    temas = dados["temas"]
    dia_do_ano = datetime.date.today().timetuple().tm_yday
    indice = (dia_do_ano - 1) % len(temas)
    return temas[indice]


def gerar_roteiro(tema: str) -> str:
    api_key = os.environ["GEMINI_API_KEY"]
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{MODELO_GEMINI}:generateContent?key={api_key}"
    )

    prompt = f"""Escreva o roteiro de um episódio de podcast em português do Brasil, \
com aproximadamente {PALAVRAS_ALVO} palavras (para dar uns 5 minutos falados).

Tema do dia: "{tema}"

Regras:
- Fale como se fosse UM apresentador só, tom natural e conversacional, como quem está \
explicando pra um amigo curioso, sem parecer um texto lido.
- Comece com uma abertura curta e envolvente (sem dizer "bem-vindos ao podcast" de forma clichê).
- Aborde o tema de forma ampla, trazendo contexto, um ou dois exemplos concretos, e uma reflexão final.
- NÃO use marcações como [música], [pausa], títulos, ou formatação markdown — é só o texto \
corrido que será lido em voz alta.
- Termine com uma despedida breve.
"""

    corpo = {"contents": [{"parts": [{"text": prompt}]}]}
    resposta = requests.post(url, json=corpo, timeout=60)
    resposta.raise_for_status()
    dados = resposta.json()
    return dados["candidates"][0]["content"]["parts"][0]["text"].strip()


async def texto_para_audio(texto: str, caminho_saida: str):
    comunicador = edge_tts.Communicate(texto, VOZ)
    await comunicador.save(caminho_saida)


def enviar_para_telegram(caminho_audio: str, tema: str, link_repo: str):
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    url = f"https://api.telegram.org/bot{token}/sendAudio"

    legenda = f"🎙️ Podcast do dia\n\n*Tema:* {tema}\n\n🔗 {link_repo}"

    with open(caminho_audio, "rb") as audio_file:
        resposta = requests.post(
            url,
            data={"chat_id": chat_id, "caption": legenda, "parse_mode": "Markdown"},
            files={"audio": audio_file},
            timeout=60,
        )
    resposta.raise_for_status()
    print("Enviado para o Telegram com sucesso.")


def main():
    hoje = datetime.date.today().isoformat()
    pasta_episodio = Path("episodes") / hoje
    pasta_episodio.mkdir(parents=True, exist_ok=True)

    tema = escolher_tema_do_dia()
    print(f"Tema de hoje: {tema}")

    roteiro = gerar_roteiro(tema)
    caminho_roteiro = pasta_episodio / "roteiro.md"
    caminho_roteiro.write_text(roteiro, encoding="utf-8")
    print(f"Roteiro salvo em {caminho_roteiro}")

    caminho_audio = pasta_episodio / "podcast.mp3"
    asyncio.run(texto_para_audio(roteiro, str(caminho_audio)))
    print(f"Áudio salvo em {caminho_audio}")

    repo = os.environ.get("GITHUB_REPOSITORY", "SEU_USUARIO/SEU_REPO")
    link_repo = f"https://github.com/{repo}/tree/main/episodes/{hoje}"

    enviar_para_telegram(str(caminho_audio), tema, link_repo)


if __name__ == "__main__":
    main()
