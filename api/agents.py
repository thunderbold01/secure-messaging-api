"""
Thunderbold_AI - Sistema de Agentes
Arquitetura: Router -> Specialist Agents -> Tools (web search, web fetch)
"""
import os
import json
import re
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS

OLLAMA_URL = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
DEFAULT_MODEL = os.environ.get('OLLAMA_MODEL', 'huihui_ai/qwen3-abliterated:4b')
VISION_MODEL = 'minicpm-v:vision'

# ==========================================
# TOOLS - Web Search, Web Fetch, Web Test
# ==========================================

def web_search(query, max_results=5):
    """Busca na web via DuckDuckGo"""
    try:
        from ddgs import DDGS
        ddgs = DDGS()
        results = ddgs.text(query, max_results=max_results)
        formatted = []
        for r in results:
            formatted.append({
                'title': r.get('title', ''),
                'url': r.get('href', r.get('link', '')),
                'snippet': r.get('body', r.get('snippet', '')),
            })
        return formatted if formatted else [{'title': 'Nenhum resultado', 'url': '', 'snippet': f'Pesquisa por: {query}'}]
    except Exception as e:
        print(f"DDG Error: {e}")
        try:
            import requests as req
            r = req.get(f'https://lite.duckduckgo.com/lite/?q={query}', headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(r.text, 'html.parser')
            results = []
            for link in soup.select('a.result-link')[:max_results]:
                results.append({'title': link.get_text(strip=True), 'url': link.get('href', ''), 'snippet': ''})
            return results if results else [{'title': 'Fallback search', 'url': '', 'snippet': f'Pesquisa por: {query}'}]
        except Exception as e2:
            return [{'error': str(e), 'fallback_error': str(e2)}]


def web_fetch(url, max_chars=3000):
    """Busca conteudo de uma pagina web"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            tag.decompose()
        text = soup.get_text(separator='\n', strip=True)
        return text[:max_chars]
    except Exception as e:
        return f"Erro ao buscar pagina: {str(e)}"


def web_test(url):
    """Testa conectividade e resposta de um servidor"""
    results = {'url': url}
    try:
        r = requests.get(url, timeout=10, allow_redirects=True)
        results['status'] = r.status_code
        results['headers'] = dict(r.headers)
        results['response_time'] = r.elapsed.total_seconds()
        results['content_type'] = r.headers.get('content-type', 'unknown')
        results['size'] = len(r.content)
        results['ok'] = r.status_code < 400
    except requests.exceptions.ConnectionError:
        results['ok'] = False
        results['error'] = 'Falha na conexao'
    except requests.exceptions.Timeout:
        results['ok'] = False
        results['error'] = 'Timeout (>10s)'
    except Exception as e:
        results['ok'] = False
        results['error'] = str(e)
    return results


# ==========================================
# AGENT DEFINITIONS
# ==========================================

AGENTS = {
    'router': {
        'name': 'Router',
        'persona': 'Analista de intencao. Responda APENAS com JSON: {"agent":"nome_do_agente","reason":"motivo"}',
        'task': 'Classificar a mensagem do usuario e direcionar para o agente correto',
        'specialization': 'Classificacao e roteamento',
        'model': DEFAULT_MODEL,
    },
    'websearch': {
        'name': 'WebSearch',
        'persona': 'Pesquisador web. Voce busca informacoes na internet e resume os resultados de forma clara e direta.',
        'task': 'Pesquisar informacoes atuais na web e fornecer respostas baseadas em fontes reais',
        'specialization': 'Noticias, informacoes atuais, fatos, dados publicos',
        'model': DEFAULT_MODEL,
        'tools': ['web_search'],
    },
    'webfetch': {
        'name': 'WebFetch',
        'persona': 'Analista de conteudo web. Voce visita paginas web, extrai informacoes e analisa o conteudo.',
        'task': 'Aceder a URLs especificas, extrair e analisar conteudo de paginas web',
        'specialization': 'Analise de paginas, extrair dados de sites, verificar conteudo',
        'model': DEFAULT_MODEL,
        'tools': ['web_fetch'],
    },
    'webtest': {
        'name': 'WebTest',
        'persona': 'Engenheiro de testes web. Voce testa servidores, analisa APIs, verifica conectividade e status HTTP.',
        'task': 'Testar endpoints, servers, APIs, verificar status e performance',
        'specialization': 'Testes de servidor, APIs, conectividade, HTTPS, DNS',
        'model': DEFAULT_MODEL,
        'tools': ['web_test'],
    },
    'coder': {
        'name': 'Coder',
        'persona': 'Programador expert. Voce ajuda com codigo, debug, arquitetura, e explica conceitos tecnicos de forma simples.',
        'task': 'Escrever, explicar e corrigir codigo em qualquer linguagem',
        'specialization': 'Programacao, debugging, arquitetura, APIs, databases',
        'model': DEFAULT_MODEL,
    },
    'researcher': {
        'name': 'Researcher',
        'persona': 'Pesquisador academico. Voce analisa topics em profundidade, pesquisa na web e apresenta analises detalhadas com fontes.',
        'task': 'Pesquisa profunda sobre qualquer tema, combinando informacoes de multiplos sites',
        'specialization': 'Pesquisa academica, analise de dados, comparativos, tutoriais',
        'model': DEFAULT_MODEL,
        'tools': ['web_search', 'web_fetch'],
    },
    'general': {
        'name': 'General',
        'persona': 'Thunderbold_AI, assistente inteligente e amigavel. Fale em portugues, seja util e direto.',
        'task': 'Conversa geral, perguntas simples, calculos, traducoes, ajudas do dia a dia',
        'specialization': 'Conversa geral, matematica, traducoes, conversao',
        'model': DEFAULT_MODEL,
    },
}


# ==========================================
# OLLAMA CALL
# ==========================================

def call_ollama(messages, model=None):
    """Chama Ollama com lista de mensagens"""
    model = model or DEFAULT_MODEL
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                'model': model,
                'messages': messages,
                'stream': False,
                'options': {'temperature': 0.7, 'num_predict': 500},
            },
            timeout=45,
        )
        if resp.status_code == 200:
            data = resp.json()
            content = data.get('message', {}).get('content', '').strip()
            thinking = data.get('message', {}).get('thinking', '').strip()
            return content or thinking or None
    except Exception as e:
        print(f"Ollama error: {e}")
    return None


# ==========================================
# ROUTER - decide qual agente usar
# ==========================================

ROUTER_PROMPT = """Voce e o Router do Thunderbold_AI. Analise a mensagem do usuario e escolha o agente correto.

AGENTES DISPONIVEIS:
- websearch: Para perguntas que precisam de informacoes ATUAIS da internet (noticias, preco, status, data atual)
- webfetch: Quando o usuario da uma URL e quer saber o conteudo dela
- webtest: Quando o usuario quer TESTAR um servidor, API, URL, ou verificar conectividade
- coder: Para perguntas sobre programacao, codigo, debug, APIs, banco de dados
- researcher: Para pesquisas PROFUNDAS que precisam de multiplas fontes e analise detalhada
- general: Para conversa geral, calculas, traducoes, perguntas simples

Responda APENAS com JSON: {"agent":"nome","reason":"motivo"}

Exemplos:
- "Qual e o preco do bitcoin?" -> {"agent":"websearch","reason":"precisa de dados atuais da web"}
- "Abre este site e ve o que tem" -> {"agent":"webfetch","reason":"usuario forneceu URL para analisar"}
- "Testa se o servidor esta no ar" -> {"agent":"webtest","reason":"teste de conectividade"}
- "Escreve uma funcao em Python" -> {"agent":"coder","reason":"programacao"}
- "Pesquisa tudo sobre inteligencia artificial" -> {"agent":"researcher","reason":"pesquisa profunda"}
- "Ola, como vai?" -> {"agent":"general","reason":"conversa geral"}
"""


def route_message(user_message):
    """Decide qual agente usar - primeiro keywords, depois Ollama"""
    msg_lower = user_message.lower()
    
    # Fast keyword routing (no Ollama needed)
    url_pattern = re.findall(r'https?://[^\s]+', user_message)
    
    if url_pattern:
        if any(w in msg_lower for w in ['test', 'teste', 'status', 'verificar', 'checar']):
            return 'webtest', 'URL detected + test keywords'
        return 'webfetch', 'URL detected in message'
    
    if any(w in msg_lower for w in ['testa', 'teste', 'servidor', 'server', 'api no ar', 'connectivity', 'verificar se']):
        return 'webtest', 'Testing keywords detected'
    
    if any(w in msg_lower for w in ['noticia', 'preco', 'valor', 'cotação', 'bitcoin', 'dólar', 'euro', 'clima', 'tempo', 'hoje', 'agora', 'atual', 'ultimas']):
        return 'websearch', 'Current event keywords detected'
    
    if any(w in msg_lower for w in ['pesquisa', 'pesquisar', 'estudo', 'analise detalhada', 'comparar', 'comparativo', 'tudo sobre']):
        return 'researcher', 'Research keywords detected'
    
    if any(w in msg_lower for w in ['código', 'code', 'função', 'function', 'programa', 'python', 'javascript', 'html', 'css', 'api', 'debug', 'erro', 'bug']):
        return 'coder', 'Programming keywords detected'
    
    # Fallback: general conversation (no Ollama routing needed)
    return 'general', 'No specific keywords matched'


# ==========================================
# AGENT EXECUTION
# ==========================================

def execute_agent(agent_name, user_message, images=None):
    """Executa um agente especifico com ferramentas"""
    agent = AGENTS.get(agent_name, AGENTS['general'])
    tools_used = []
    tool_context = ''

    # Web Search
    if 'web_search' in agent.get('tools', []):
        search_results = web_search(user_message, max_results=5)
        if search_results and 'error' not in search_results[0]:
            tools_used.append('web_search')
            tool_context = '\n\nRESULTADOS DA PESQUISA WEB:\n'
            for i, r in enumerate(search_results, 1):
                tool_context += f"\n{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}\n"

    # Web Fetch - detecta URLs na mensagem
    if 'web_fetch' in agent.get('tools', []):
        urls = re.findall(r'https?://[^\s]+', user_message)
        if urls:
            for url in urls[:2]:
                content = web_fetch(url)
                tools_used.append('web_fetch')
                tool_context += f'\n\nCONTEUDO DE {url}:\n{content[:2000]}\n'

    # Web Test - detecta URLs para teste
    if 'web_test' in agent.get('tools', []):
        urls = re.findall(r'https?://[^\s]+', user_message)
        if not urls:
            urls = re.findall(r'(?:localhost|127\.0\.0\.1|[\w.-]+\.\w{2,})[^\s]*', user_message)
            urls = [('http://' + u if not u.startswith('http') else u) for u in urls]
        if urls:
            for url in urls[:3]:
                test_result = web_test(url)
                tools_used.append('web_test')
                status = 'OK' if test_result.get('ok') else 'FALHOU'
                tool_context += f'\n\nTESTE DE {url}:\n'
                tool_context += f'  Status: {test_result.get("status", "N/A")} ({status})\n'
                tool_context += f'  Tempo: {test_result.get("response_time", "N/A")}s\n'
                tool_context += f'  Tamanho: {test_result.get("size", "N/A")} bytes\n'
                if test_result.get('error'):
                    tool_context += f'  Erro: {test_result["error"]}\n'

    # Monta mensagens para o agente
    system_msg = f"""{agent['persona']}

TAREFA: {agent['task']}
ESPECIALIDADE: {agent['specialization']}

REGRAS:
- Responda em portugues
- Seja direto e util (2-5 frases)
- Se tem dados da web, use-os como referencia
- Se nao tem dados suficientes, diga o que sabe e sugira pesquisar mais
"""
    if tool_context:
        system_msg += f'\nDADOS OBTIDOS:{tool_context}'

    messages = [
        {'role': 'system', 'content': system_msg},
        {'role': 'user', 'content': user_message},
    ]

    reply = call_ollama(messages, model=agent['model'])

    return {
        'reply': reply or 'Nao foi possivel processar.',
        'agent': agent_name,
        'agent_name': agent['name'],
        'tools_used': tools_used,
        'persona': agent['persona'],
    }


# ==========================================
# MAIN ENTRY POINT
# ==========================================

def process_message(user_message, user_id=None, images=None):
    """Ponto de entrada principal - route + execute"""
    agent_name, reason = route_message(user_message)
    result = execute_agent(agent_name, user_message, images)
    result['routing_reason'] = reason
    return result
