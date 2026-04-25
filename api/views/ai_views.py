import json
import requests
import hashlib
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

GEMINI_API_KEY = 'AIzaSyDNEn94MQPOwZF8tKN_iBU9_U9OAjr7h-g'

# URL CORRETA - use "models/" no path e ":generateContent" no final
GEMINI_MODELS = [
    "models/gemini-2.5-flash",        # Mais novo
    "models/gemini-2.0-flash",        # Estável
    "models/gemini-flash-latest",     # Latest
]

user_conversations = {}

def get_user_history(user_id):
    return user_conversations.get(str(user_id), [])

def save_user_history(user_id, role, content):
    uid = str(user_id)
    if uid not in user_conversations:
        user_conversations[uid] = []
    user_conversations[uid].append({"role": role, "parts": [{"text": content}]})
    if len(user_conversations[uid]) > 10:
        user_conversations[uid] = user_conversations[uid][-10:]

def clear_user_history(user_id):
    user_conversations.pop(str(user_id), None)

def call_gemini(mensagem, history):
    """Tenta chamar Gemini com diferentes modelos"""
    contents = [
        {"role": "user", "parts": [{"text": "Você é Thunderbold_AI, um assistente em português. Responda curto (2-3 frases)."}]},
        {"role": "model", "parts": [{"text": "Entendi! Sou Thunderbold_AI. Como posso ajudar?"}]}
    ] + history + [
        {"role": "user", "parts": [{"text": mensagem}]}
    ]
    
    for model in GEMINI_MODELS:
        try:
            # URL correta: models/nome-modelo:generateContent
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"
            
            response = requests.post(
                f"{url}?key={GEMINI_API_KEY}",
                json={
                    "contents": contents,
                    "generationConfig": {"temperature": 0.7, "maxOutputTokens": 100}
                },
                timeout=15
            )
            
            if response.status_code == 200:
                result = response.json()
                reply = result['candidates'][0]['content']['parts'][0]['text']
                return reply.encode('utf-8', errors='ignore').decode('utf-8', errors='ignore').strip()
            
        except:
            continue
    
    return None


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def chat_with_ai(request):
    try:
        data = json.loads(request.body)
        mensagem = data.get('mensagem', '').strip()
        limpar = data.get('limpar', False)
        
        if limpar:
            clear_user_history(request.user.id)
            return Response({'reply': '🧹 Histórico limpo!'})
        
        if not mensagem:
            return Response({'erro': 'Mensagem vazia'}, status=400)
        
        if len(mensagem) > 500:
            mensagem = mensagem[:500]
        
        cache_key = f"ai_{hashlib.md5(mensagem.encode()).hexdigest()}"
        cached = cache.get(cache_key)
        if cached:
            return Response({'reply': cached, 'cached': True})
        
        history = get_user_history(request.user.id)
        reply = call_gemini(mensagem, history)
        
        if reply:
            save_user_history(request.user.id, 'user', mensagem)
            save_user_history(request.user.id, 'model', reply)
            cache.set(cache_key, reply, 300)
            return Response({'reply': reply})
        else:
            fallback = "👋 Olá! Sou Thunderbold_AI. Estou com alta demanda agora. Tente novamente em alguns segundos!"
            return Response({'reply': fallback, 'fallback': True})
            
    except Exception as e:
        return Response({'reply': '❌ Erro interno. Tente novamente.'}, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ai_status(request):
    return Response({'online': True, 'model': 'Gemini-2.0-Flash', 'provider': 'Google'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def ai_clear_history(request):
    clear_user_history(request.user.id)
    return Response({'reply': '🧹 Histórico limpo!'})