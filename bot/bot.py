import discord
from discord.ext import tasks, commands
import requests
from bs4 import BeautifulSoup
import asyncio
import json
import os
import logging
from flask import Flask
from threading import Thread
from dotenv import load_dotenv

# Carregar variáveis de ambiente do arquivo .env
load_dotenv()

# Configuração de Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Obter token e ID do canal a partir das variáveis de ambiente
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# URL da página de concursos
URL = 'https://www.pciconcursos.com.br/concursos/sul/'

# Intenções do Discord
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # Necessário para acessar o conteúdo das mensagens

bot = commands.Bot(command_prefix='!', intents=intents)

# Critérios de escolaridade
ESCOLARIDADES_DE_INTERESSE = [
    "Alfabetizado / Fundamental / Médio / Técnico / Superior",
    "Alfabetizado / Médio / Técnico / Superior",
    "Fundamental / Médio / Superior",
    "Fundamental / Médio / Técnico / Superior",
    "Fundamental / Superior",
    "Fundamental Incompleto / Fundamental / Médio / Técnico / Superior",
    "Médio / Superior",
    "Médio / Técnico / Superior"
]

# Critérios de cargos específicos
CARGOS_DE_INTERESSE = [
    "Médico ESF",
    "Médico I",
    "Vários Cargos"
]

# Arquivo para armazenar os links de concursos já notificados
NOTIFICADOS_FILE = 'notificados.json'

def carregar_notificados():
    """
    Carrega a lista de concursos já notificados a partir do arquivo JSON.

    Returns:
        list: Lista de links de concursos já notificados.
    """
    if os.path.exists(NOTIFICADOS_FILE):
        try:
            with open(NOTIFICADOS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, list):
                    logging.info(f"Carregado {len(data)} concursos já notificados.")
                    return data
                else:
                    logging.warning(f"{NOTIFICADOS_FILE} não é uma lista válida. Reiniciando a lista de notificados.")
                    return []
        except json.JSONDecodeError:
            logging.warning(f"Erro de decodificação no {NOTIFICADOS_FILE}. Reiniciando a lista de notificados.")
            return []
    return []

def salvar_notificados():
    """
    Salva a lista de concursos já notificados no arquivo JSON.
    """
    try:
        with open(NOTIFICADOS_FILE, 'w', encoding='utf-8') as f:
            json.dump(notificados, f, ensure_ascii=False, indent=4)
        logging.info(f"Salvo {len(notificados)} concursos notificados.")
    except Exception as e:
        logging.error(f"Erro ao salvar {NOTIFICADOS_FILE}: {e}")

# Carregar concursos já notificados
notificados = carregar_notificados()

def fetch_concursos():
    """
    Faz uma requisição para a URL fornecida e extrai os concursos da página.

    Returns:
        list: Lista de dicionários contendo detalhes de cada concurso.
    """
    try:
        response = requests.get(URL)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        logging.error(f"Erro ao acessar a página: {e}")
        return []

    soup = BeautifulSoup(response.text, 'html.parser')
    concursos = []

    # Encontrar todas as divs com classe 'na' que contêm os concursos
    items = soup.find_all('div', class_='na')

    for item in items:
        # Extrair o link do concurso
        link = item.get('data-url', '')
        if not link:
            a_tag = item.find('a')
            if a_tag and a_tag.get('href'):
                link = a_tag['href']
            else:
                link = 'Sem Link'

        # Extrair o título do concurso
        a_tag = item.find('div', class_='ca').find('a') if item.find('div', class_='ca') else None
        titulo = a_tag.get('title', '').strip() if a_tag else 'Sem Título'

        # Extrair o estado (UF)
        estado_tag = item.find('div', class_='cc')
        estado = estado_tag.text.strip() if estado_tag else 'Não Informado'

        # Extrair vagas, salário, posições e escolaridade
        cd_tag = item.find('div', class_='cd')
        if cd_tag:
            # Extrair texto antes do <br> para vagas e salário
            vagas_salario = cd_tag.get_text(separator='\n').split('\n')[0].strip()

            # Extrair posições e escolaridade
            spans = cd_tag.find_all('span')
            posicoes = spans[0].get_text(separator=', ').strip() if len(spans) > 0 else 'Não Informado'
            escolaridade = spans[1].get_text().strip() if len(spans) > 1 else 'Não Informado'
        else:
            vagas_salario = 'Não Informado'
            posicoes = 'Não Informado'
            escolaridade = 'Não Informado'

        # Extrair data limite para inscrições
        data_tag = item.find('div', class_='ce').find('span') if item.find('div', class_='ce') else None
        inscricoes_ate = data_tag.text.strip() if data_tag else 'Não Informado'

        concursos.append({
            'titulo': titulo,
            'link': link,
            'estado': estado,
            'vagas_salario': vagas_salario,
            'posicoes': posicoes,
            'escolaridade': escolaridade,
            'inscricoes_ate': inscricoes_ate
        })

    logging.info(f"Total de concursos encontrados: {len(concursos)}")
    return concursos

async def enviar_notificacao(concurso, channel, teste=False):
    """
    Envia uma notificação no canal Discord com os detalhes do concurso.

    Args:
        concurso (dict): Dicionário contendo detalhes do concurso.
        channel (discord.TextChannel): Canal onde a notificação será enviada.
        teste (bool): Se True, adiciona uma identificação de teste na notificação.
    """
    try:
        titulo = concurso['titulo']
        if teste:
            titulo = f"[TESTE] {titulo}"

        embed = discord.Embed(
            title=titulo,
            url=concurso['link'],
            description=(
                f"**Estado:** {concurso['estado']}\n"
                f"**Vagas e Salário:** {concurso['vagas_salario']}\n"
                f"**Posições:** {concurso['posicoes']}\n"
                f"**Escolaridade:** {concurso['escolaridade']}\n"
                f"**Inscrições até:** {concurso['inscricoes_ate']}"
            ),
            color=0x00ff00  # Cor verde
        )
        # Configurar o autor do embed com o nome e avatar do bot
        embed.set_author(name=bot.user.name, icon_url=bot.user.avatar.url if bot.user.avatar else None)
        # Configurar o rodapé do embed com o avatar do bot
        embed.set_footer(text="Concurso Público", icon_url=bot.user.avatar.url if bot.user.avatar else None)
        await channel.send(embed=embed)
        logging.info(f"Notificação enviada para: {concurso['titulo']}")
    except Exception as e:
        logging.error(f"Erro ao enviar notificação para {concurso['titulo']}: {e}")

async def enviar_notificacao_teste():
    """
    Envia uma notificação de teste para verificar se o bot está funcionando corretamente.
    """
    concursos = fetch_concursos()
    if not concursos:
        logging.info('Nenhum concurso encontrado para o teste.')
        return

    primeiro_concurso = concursos[0]
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await enviar_notificacao(primeiro_concurso, channel, teste=True)
        logging.info('Notificação de teste enviada com sucesso.')
    else:
        logging.error('Canal não encontrado. Verifique o CHANNEL_ID.')
        
@bot.command(name='testar')
@commands.has_permissions(administrator=True)
async def testar(ctx):
    """
    Envia uma notificação de teste no canal onde o comando foi chamado.
    """
    concursos = fetch_concursos()
    if not concursos:
        await ctx.send("Nenhum concurso encontrado para o teste.")
        return

    primeiro_concurso = concursos[0]
    await enviar_notificacao(primeiro_concurso, ctx.channel, teste=True)
    await ctx.send("Notificação de teste enviada com sucesso.")

@bot.event
async def on_ready():
    logging.info(f'Bot conectado como {bot.user}')
    # Enviar notificação de teste
    await enviar_notificacao_teste()
    # Iniciar a verificação periódica
    check_concursos.start()

@tasks.loop(minutes=10)  # Intervalo de verificação
async def check_concursos():
    global notificados
    concursos = fetch_concursos()
    if not concursos:
        logging.info('Nenhum concurso encontrado.')
        return

    # Filtrar concursos que ainda não foram notificados (usando 'link' como identificador único)
    novos_concursos = [c for c in concursos if c['link'] not in notificados]

    # Aplicar o filtro baseado nos critérios de interesse
    concursos_filtrados = []
    for concurso in novos_concursos:
        # Verificar se a escolaridade está na lista de interesse
        if concurso['escolaridade'] in ESCOLARIDADES_DE_INTERESSE:
            concursos_filtrados.append(concurso)
            continue  # Já atende ao critério, não precisa verificar os cargos

        # Verificar se algum dos cargos está na lista de interesse
        # Dividir os cargos por vírgula e verificar individualmente
        cargos = [cargo.strip() for cargo in concurso['posicoes'].split(',')]
        if any(cargo in CARGOS_DE_INTERESSE for cargo in cargos):
            concursos_filtrados.append(concurso)

    # Enviar notificações para os concursos filtrados
    if concursos_filtrados:
        channel = bot.get_channel(CHANNEL_ID)
        for concurso in concursos_filtrados:
            await enviar_notificacao(concurso, channel)
            notificados.append(concurso['link'])  # Usando 'link' como identificador único
        salvar_notificados()
        logging.info(f'{len(concursos_filtrados)} novos concursos notificados.')
    else:
        logging.info('Nenhum novo concurso corresponde aos critérios de interesse.')

# Função para iniciar o servidor web com Flask
def run_flask():
    app = Flask('')

    @app.route('/')
    def home():
        return "Bot está online!"

    # Configurar Flask para rodar sem logs desnecessários
    import logging as flask_logging
    log = flask_logging.getLogger('werkzeug')
    log.setLevel(flask_logging.ERROR)

    app.run(host='0.0.0.0', port=8080)

# Iniciar o servidor Flask em uma thread separada
flask_thread = Thread(target=run_flask)
flask_thread.start()

# Iniciar o bot Discord
bot.run(TOKEN)
