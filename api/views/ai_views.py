import json
import requests
import hashlib
from django.conf import settings
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

LM_STUDIO_URL = getattr(settings, 'LM_STUDIO_URL', 'http://localhost:1234')
LM_STUDIO_TIMEOUT = getattr(settings, 'LM_STUDIO_TIMEOUT', 15)

# Cache de histórico por usuário (em memória - usar Redis em produção)
user_conversations = {}


def get_user_history(user_id):
    """Recupera histórico de conversa do usuário (últimas 10 mensagens)"""
    return user_conversations.get(str(user_id), [])


def save_user_history(user_id, role, content):
    """Salva mensagem no histórico do usuário"""
    uid = str(user_id)
    if uid not in user_conversations:
        user_conversations[uid] = []
    
    user_conversations[uid].append({"role": role, "content": content})
    
    # Manter apenas últimas 12 mensagens (6 trocas)
    if len(user_conversations[uid]) > 12:
        user_conversations[uid] = user_conversations[uid][-12:]


def clear_user_history(user_id):
    """Limpa histórico do usuário"""
    uid = str(user_id)
    if uid in user_conversations:
        user_conversations[uid] = []


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    """
    Chat individual com IA.
    Cada usuário tem seu próprio histórico de conversa.
    """
    try:
        data = json.loads(request.body)
        mensagem = data.get('mensagem', '').strip()
        limpar = data.get('limpar', False)  # Opção para limpar histórico
        
        user_id = str(request.user.id)
        
        # Limpar histórico se solicitado
        if limpar:
            clear_user_history(request.user.id)
            return Response({'reply': '🧹 Histórico limpo! Nova conversa iniciada.'})
        
        if not mensagem:
            return Response({'erro': 'Mensagem vazia'}, status=400)
        
        # Limitar tamanho
        if len(mensagem) > 500:
            mensagem = mensagem[:500]
        
        # Cache para mensagem idêntica do mesmo usuário
        cache_key = f"ai_{user_id}_{hashlib.md5(mensagem.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            # Salvar no histórico mesmo sendo cache
            save_user_history(request.user.id, 'user', mensagem)
            save_user_history(request.user.id, 'assistant', cached)
            return Response({'reply': cached, 'cached': True})
        
        # Recuperar histórico do usuário
        history = get_user_history(request.user.id)
        
        # Construir mensagens para o modelo
        messages = [
            {
                "role": "system",
                "content": (
                    "Você é um assistente amigável e útil. "
                    "Responde em português de forma curta e direta. "
                    "Máximo 2-3 frases. Seja natural como um amigo."
                )
            }
        ]
        
        # Adicionar histórico da conversa
        messages.extend(history)
        
        # Adicionar nova mensagem
        messages.append({"role": "user", "content": mensagem})
        
        # Chamar LM Studio
        response = requests.post(
            f"{LM_STUDIO_URL}/v1/chat/completions",
            json={
                "messages": messages,
                "temperature": 0.5,
                "max_tokens": 100,
                "stream": False
            },
            timeout=LM_STUDIO_TIMEOUT
        )
        
        if response.status_code == 200:
            result = response.json()
            reply = result['choices'][0]['message']['content'].strip()
            
            # Salvar no histórico
            save_user_history(request.user.id, 'user', mensagem)
            save_user_history(request.user.id, 'assistant', reply)
            
            # Cache por 3 minutos
            cache.set(cache_key, reply, 180)
            
            return Response({
                'reply': reply,
                'model': result.get('model', 'local'),
                'tokens': result.get('usage', {}).get('total_tokens', 0),
                'historico_tamanho': len(get_user_history(request.user.id))
            })
        else:
            return Response({'erro': 'Erro no modelo'}, status=502)
            
    except requests.exceptions.Timeout:
        return Response({
            'erro': 'Modelo demorou. Tente mensagem mais curta.',
            'fallback': True
        }, status=504)
    except requests.exceptions.ConnectionError:
        return Response({
            'erro': 'LM Studio offline. Ligue o servidor local.',
            'fallback': True
        }, status=503)
    except Exception as e:
        return Response({'erro': str(e)}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_status(request):
    """Status do LM Studio + info do usuário"""
    user_id = str(request.user.id)
    history_size = len(get_user_history(request.user.id))
    
    try:
        response = requests.get(f"{LM_STUDIO_URL}/v1/models", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models = data.get('data', [])
            return Response({
                'online': True,
                'modelo': models[0]['id'] if models else 'desconhecido',
                'seu_historico': history_size,
                'usuarios_ativos': len(user_conversations)
            })
        return Response({'online': False, 'seu_historico': history_size})
    except:
        return Response({'online': False, 'seu_historico': history_size})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_clear_history(request):
    """Limpa histórico do usuário"""
    clear_user_history(request.user.id)
    return Response({'reply': '🧹 Histórico limpo!'})