# Podcast Diário → GitHub → Telegram

Todo dia, automaticamente:
1. Escolhe um tema de `topics.json` (cíclico, 1 por dia)
2. Gera um roteiro de ~5 minutos usando a API da Anthropic (Claude)
3. Converte o roteiro em áudio com `edge-tts` (gratuito, vozes da Microsoft)
4. Salva tudo em `episodes/AAAA-MM-DD/` e commita no repositório
5. Envia o áudio para o grupo do Telegram

## Como configurar

### 1. Suba esses arquivos para um repositório no GitHub
Crie um repositório novo (pode ser privado) e envie todo o conteúdo desta pasta para ele.

### 2. Crie o bot do Telegram
- No Telegram, fale com **@BotFather**, envie `/newbot` e siga as instruções.
- Guarde o **token** que ele fornecer.
- Adicione o bot ao seu grupo do Telegram.
- Descubra o **Chat ID** do grupo acessando no navegador:
  `https://api.telegram.org/bot<SEU_TOKEN>/getUpdates`
  (envie uma mensagem no grupo antes, para aparecer nos updates). O `chat.id` do grupo
  geralmente é um número negativo, tipo `-1001234567890`.

### 3. Pegue uma chave da API da Anthropic
- Crie uma conta em https://console.anthropic.com se ainda não tiver.
- Gere uma API key.

### 4. Configure os Secrets no GitHub
No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
Crie estes três:

| Nome | Valor |
|---|---|
| `ANTHROPIC_API_KEY` | sua chave da API da Anthropic |
| `TELEGRAM_BOT_TOKEN` | o token do bot que o BotFather te deu |
| `TELEGRAM_CHAT_ID` | o Chat ID do grupo (com o sinal de menos, se tiver) |

### 5. Pronto
O workflow em `.github/workflows/daily-podcast.yml` já está agendado para rodar
todo dia às 09:00 (horário de Brasília). Para testar sem esperar, vá na aba
**Actions** do repositório → selecione "Podcast Diário" → **Run workflow**.

## Customizações fáceis

- **Mudar os temas**: edite `topics.json`. A ordem define qual dia usa qual tema.
- **Mudar a voz**: troque `VOZ` em `generate_podcast.py`. Para listar todas as vozes
  disponíveis em PT-BR, rode localmente: `edge-tts --list-voices | grep pt-BR`
- **Mudar o horário**: edite o `cron` em `daily-podcast.yml` (horário é em UTC).
- **Mudar a duração**: ajuste `PALAVRAS_ALVO` em `generate_podcast.py`
  (regra prática: ~150 palavras por minuto de fala).
