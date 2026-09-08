import json
import os
import hashlib
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.agents import process_message, web_search, web_fetch, web_test, AGENTS

user_conversations = {}


def get_user_history(user_id):
    return user_conversations.get(str(user_id), [])


def save_user_history(user_id, role, content):
    uid = str(user_id)
    if uid not in user_conversations:
        user_conversations[uid] = []
    user_conversations[uid].append({'role': role, 'content': content})
    if len(user_conversations[uid]) > 10:
        user_conversations[uid] = user_conversations[uid][-10:]


def clear_user_history(user_id):
    user_conversations.pop(str(user_id), None)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    try:
        data = json.loads(request.body)
        mensagem = data.get('mensagem', '').strip()
        limpar = data.get('limpar', False)

        if limpar:
            clear_user_history(request.user.id)
            return Response({'reply': 'Historico limpo!'})

        if not mensagem:
            return Response({'erro': 'Mensagem vazia'}, status=400)

        if len(mensagem) > 1000:
            mensagem = mensagem[:1000]

        cache_key = f"ai_{hashlib.md5(mensagem.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            return Response({'reply': cached, 'cached': True, 'provider': 'cache'})

        result = process_message(mensagem, user_id=request.user.id)

        reply = result.get('reply', 'Erro ao processar.')
        agent = result.get('agent', 'general')
        agent_name = result.get('agent_name', 'General')
        tools = result.get('tools_used', [])
        reason = result.get('routing_reason', '')

        save_user_history(request.user.id, 'user', mensagem)
        save_user_history(request.user.id, 'assistant', reply)
        cache.set(cache_key, reply, 300)

        return Response({
            'reply': reply,
            'provider': 'ollama',
            'agent': agent,
            'agent_name': agent_name,
            'tools_used': tools,
            'routing_reason': reason,
        })

    except Exception as e:
        print(f'AI Error: {e}')
        import traceback
        traceback.print_exc()
        return Response({'reply': 'Erro interno. Tente novamente.', 'provider': 'error'}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_web_search(request):
    """Endpoint dedicado para web search"""
    try:
        data = json.loads(request.body)
        query = data.get('query', '').strip()
        if not query:
            return Response({'erro': 'Query obrigatoria'}, status=400)
        results = web_search(query, max_results=data.get('max_results', 5))
        return Response({'results': results, 'query': query})
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_web_fetch(request):
    """Endpoint dedicado para web fetch"""
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        if not url:
            return Response({'erro': 'URL obrigatoria'}, status=400)
        content = web_fetch(url)
        return Response({'content': content, 'url': url})
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_web_test(request):
    """Endpoint dedicado para web test"""
    try:
        data = json.loads(request.body)
        url = data.get('url', '').strip()
        if not url:
            return Response({'erro': 'URL obrigatoria'}, status=400)
        result = web_test(url)
        return Response(result)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_status(request):
    import requests as req
    ollama_online = False
    models = []
    try:
        r = req.get(f'{os.environ.get("OLLAMA_URL", "http://localhost:11434")}/api/tags', timeout=3)
        if r.status_code == 200:
            ollama_online = True
            models = [m['name'] for m in r.json().get('models', [])]
    except Exception:
        pass

    return Response({
        'online': True,
        'ollama': {'online': ollama_online, 'models': models},
        'agents': {name: {
            'name': a['name'],
            'specialization': a['specialization'],
            'tools': a.get('tools', []),
        } for name, a in AGENTS.items() if name != 'router'},
        'model': os.environ.get('OLLAMA_MODEL', 'huihui_ai/dolphin3-abliterated:8b'),
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_clear_history(request):
    clear_user_history(request.user.id)
    return Response({'reply': 'Historico limpo!'})
