"""
Thunderbold AI - Multi-Agent Architecture
Sistema de agentes especializados usando Ollama local
Modelos: QWEN (router), DOLPHIN (reasoning), MiniCPM-Vision (vision)
"""
import os
import json
import base64
import re
import requests
from typing import Optional

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")

MODELS = {
    "router": "huihui_ai/qwen3-abliterated:4b",
    "reasoning": "huihui_ai/dolphin3-abliterated:8b",
    "vision": "minicpm-v:vision",
}

SYSTEM_PROMPTS = {
    "router": """Tu és o Thunderbold Router. Analisa a pergunta do utilizador e decide QUAL agente deve tratar.

Responde APENAS com JSON valido:
{"agent": "NOME_DO_AGENTE", "reason": "razao curta"}

Agentes disponiveis:
- "vision" - quando o utilizador envia uma IMAGEM ou quer analise visual
- "web_search" - quando precisa de informacao atual da internet, noticias, precos, tempo, etc
- "reasoning" - para questoes complexas, codigo, logica, matematica, programacao, arquitetura
- "general" - conversa geral, saudacoes, perguntas simples

Exemplos:
- "Ola" -> {"agent": "general", "reason": "saudacao"}
- "Analisa esta imagem" -> {"agent": "vision", "reason": "analise de imagem"}
- "Qual e o preco do bitcoin?" -> {"agent": "web_search", "reason": "precisa de dados atualizados"}
- "Escreve um script Python" -> {"agent": "reasoning", "reason": "programacao"}
- "Como funciona RSA?" -> {"reasoning": "reasoning", "reason": "explicacao tecnica complexa"}

Responde SO o JSON, nada mais.""",

    "reasoning": """Tu és o Thunderbold_Reasoning, um especialista em raciocinio complexo, programacao e analise tecnica.
Usas o modelo DOLPHIN para respostas profundas e detalhadas.
Fala em portugues. Seja preciso, tecnico e didatico.
Podes resolver problemas de codigo, matematica, logica, arquitetura de software, seguranca, etc.""",
}

AGENT_LABELS = {
    "router": "Router (QWEN)",
    "reasoning": "Reasoning (DOLPHIN)",
    "vision": "Vision (MiniCPM-V)",
    "web_search": "Web Search",
    "general": "General (QWEN)",
}


def call_ollama(model: str, messages: list, timeout: int = 60) -> Optional[str]:
    """Chama um modelo Ollama"""
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 500},
            },
            timeout=timeout,
        )
        if response.status_code == 200:
            return response.json()["message"]["content"].strip()
    except Exception as e:
        print(f"[AGENT ERROR] Model {model}: {e}")
    return None


def web_search(query: str, max_results: int = 5) -> str:
    """Pesquisa web usando DuckDuckGo"""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "Nenhum resultado encontrado."
            output = []
            for i, r in enumerate(results, 1):
                output.append(f"{i}. **{r.get('title', '')}**\n   {r.get('body', '')}\n   Fonte: {r.get('href', '')}")
            return "\n\n".join(output)
    except Exception as e:
        return f"Erro na pesquisa web: {str(e)}"


def fetch_webpage(url: str) -> str:
    """Busca conteudo de uma pagina web"""
    try:
        import httpx
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(url, headers=headers)
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            return "\n".join(lines[:100])
    except Exception as e:
        return f"Erro ao buscar pagina: {str(e)}"


def detect_agent(mensagem: str, has_image: bool = False) -> str:
    """Usa QWEN para roteamento da tarefa"""
    if has_image:
        return "vision"

    router_prompt = [
        {"role": "system", "content": SYSTEM_PROMPTS["router"]},
        {"role": "user", "content": mensagem},
    ]
    reply = call_ollama(MODELS["router"], router_prompt, timeout=15)
    if reply:
        try:
            clean = reply.strip()
            if "```" in clean:
                clean = re.sub(r"```json?\n?", "", clean)
                clean = re.sub(r"```", "", clean)
            match = re.search(r'\{[^}]+\}', clean)
            if match:
                data = json.loads(match.group())
                agent = data.get("agent", "general")
                if agent in AGENT_LABELS:
                    return agent
        except Exception:
            pass

    lower = mensagem.lower()
    web_keywords = ["pesquisa", "search", "google", "preco", "preço", "cotação", "cotacao",
                    "noticia", "noticias", "tempo", "clima", "atual", "atualmente",
                    "ultimas", "recente", "hoje", "agora", "onde", "quanto custa",
                    "reputação", "reviews", "comparar"]
    if any(kw in lower for kw in web_keywords):
        return "web_search"

    code_keywords = ["codigo", "código", "code", "python", "javascript", "function",
                     "implementar", "algoritmo", "bug", "debug", "programa", "script",
                     "api", "endpoint", "class", "def ", "import ", "matematica", "calculo",
                     "equação", "logica", "arquitetura", "sistema"]
    if any(kw in lower for kw in code_keywords):
        return "reasoning"

    return "general"


def process_with_agent(mensagem: str, history: list = None, images_b64: list = None) -> dict:
    """Processa mensagem com o agente apropriado"""
    has_image = bool(images_b64)

    if history is None:
        history = []

    agent = detect_agent(mensagem, has_image)
    print(f"[AGENT ROUTE] '{mensagem[:50]}...' -> {agent}")

    if agent == "vision":
        return _process_vision(mensagem, images_b64)

    elif agent == "web_search":
        return _process_web_search(mensagem, history)

    elif agent == "reasoning":
        return _process_reasoning(mensagem, history)

    else:
        return _process_general(mensagem, history)


def _process_general(mensagem: str, history: list) -> dict:
    """Agente geral - usa QWEN"""
    system = "Tu és Thunderbold_AI, um assistente inteligente e amigavel. Fala em portugues. Responde curto (2-3 frases)."
    messages = [{"role": "system", "content": system}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": mensagem})

    reply = call_ollama(MODELS["router"], messages, timeout=30)
    return {
        "reply": reply or "Desculpa, nao consegui processar.",
        "provider": "ollama",
        "model": MODELS["router"],
        "agent": "general",
        "agent_label": AGENT_LABELS["general"],
    }


def _process_vision(mensagem: str, images_b64: list = None) -> dict:
    """Agente de visao - usa MiniCPM-Vision"""
    messages = [
        {
            "role": "user",
            "content": mensagem or "Descreve o que ves nesta imagem em detalhes.",
            "images": images_b64 or [],
        }
    ]
    reply = call_ollama(MODELS["vision"], messages, timeout=60)
    return {
        "reply": reply or "Nao consegui analisar a imagem.",
        "provider": "ollama",
        "model": MODELS["vision"],
        "agent": "vision",
        "agent_label": AGENT_LABELS["vision"],
    }


def _process_web_search(mensagem: str, history: list) -> dict:
    """Agente de pesquisa web - busca e sintetiza"""
    search_queries = [
        mensagem,
    ]

    results_text = ""
    for q in search_queries:
        results = web_search(q, max_results=4)
        results_text += f"\n\nResultados para '{q}':\n{results}"

    synthesis_prompt = [
        {
            "role": "system",
            "content": (
                "Tu és o Thunderbold_WebSearch. Recebeste resultados de pesquisa web. "
                "Sintetiza a informacao de forma clara e util em portugues. "
                "Cita as fontes quando relevante. Responde de forma concisa mas completa."
            ),
        },
        {"role": "user", "content": f"Pergunta original: {mensagem}\n\nResultados da pesquisa:\n{results_text}"},
    ]

    reply = call_ollama(MODELS["reasoning"], synthesis_prompt, timeout=45)
    return {
        "reply": reply or "Nao consegui sintetizar os resultados.",
        "provider": "ollama",
        "model": MODELS["reasoning"],
        "agent": "web_search",
        "agent_label": AGENT_LABELS["web_search"],
        "search_results": results_text[:500],
    }


def _process_reasoning(mensagem: str, history: list) -> dict:
    """Agente de raciocinio - usa DOLPHIN"""
    system = (
        "Tu és o Thunderbold_Reasoning, um especialista em raciocinio complexo, programacao e analise tecnica. "
        "Usas o modelo DOLPHIN para respostas profundas. "
        "Fala em portugues. Seja preciso, tecnico e didatico."
    )
    messages = [{"role": "system", "content": system}]
    for msg in history[-6:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": mensagem})

    reply = call_ollama(MODELS["reasoning"], messages, timeout=60)
    return {
        "reply": reply or "Nao consegui processar esta tarefa.",
        "provider": "ollama",
        "model": MODELS["reasoning"],
        "agent": "reasoning",
        "agent_label": AGENT_LABELS["reasoning"],
    }


def get_agents_status() -> dict:
    """Verifica status de todos os agentes e modelos"""
    status = {"agents": [], "models": {}}

    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            for m in models:
                status["models"][m["name"]] = {
                    "size": m.get("size", 0),
                    "modified": m.get("modified_at", ""),
                }
    except Exception:
        pass

    for agent_key, model_id in MODELS.items():
        available = any(model_id in name for name in status["models"])
        status["agents"].append({
            "id": agent_key,
            "label": AGENT_LABELS[agent_key],
            "model": model_id,
            "online": available,
        })

    return status
