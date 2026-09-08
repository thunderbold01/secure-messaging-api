"""
WebSocket Signaling Server para WebRTC
Corre em porta separada (8001) - server HTTP fica no 8000
Criptografia: WebRTC usa DTLS-SRTP nativo (E2E encripted)
"""
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

import django
django.setup()

from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("websockets not installed. Install with: pip install websockets")

connections = {}
rooms = {}


def get_user_from_token(token_key):
    try:
        token = Token.objects.select_related('user').get(key=token_key)
        return token.user
    except Token.DoesNotExist:
        return None


async def handler(websocket, path=None):
    user = None
    user_id = None
    room_name = None

    try:
        async for message in websocket:
            data = json.loads(message)
            msg_type = data.get('type', '')

            if msg_type == 'auth':
                token_key = data.get('token', '')
                user = get_user_from_token(token_key)
                if user:
                    user_id = str(user.id)
                    connections[user_id] = websocket
                    await websocket.send(json.dumps({
                        'type': 'connected',
                        'user_id': user_id,
                        'username': user.username,
                    }))
                else:
                    await websocket.send(json.dumps({'type': 'error', 'message': 'Auth failed'}))
                    await websocket.close()
                    return

            elif msg_type == 'join_room':
                target_id = data.get('target_user_id')
                call_type = data.get('call_type', 'voice')
                if not user_id or not target_id:
                    continue

                room_name = f'call_{min(user_id, target_id)}_{max(user_id, target_id)}'
                if room_name not in rooms:
                    rooms[room_name] = set()
                rooms[room_name].add(user_id)

                await websocket.send(json.dumps({
                    'type': 'room_joined',
                    'room': room_name,
                    'call_type': call_type,
                }))

                for uid in rooms[room_name]:
                    if uid != user_id and uid in connections:
                        await connections[uid].send(json.dumps({
                            'type': 'peer_joined',
                            'user_id': user_id,
                            'username': user.username,
                            'call_type': call_type,
                        }))

            elif msg_type in ('call_offer', 'call_answer', 'ice_candidate', 'call_reject', 'call_accept', 'call_end'):
                data['from_user_id'] = user_id
                data['from_username'] = user.username if user else 'unknown'

                if room_name and room_name in rooms:
                    for uid in rooms[room_name]:
                        if uid != user_id and uid in connections:
                            try:
                                await connections[uid].send(json.dumps(data))
                            except Exception:
                                pass

    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"Handler error: {e}")
    finally:
        if user_id and user_id in connections:
            del connections[user_id]
        if room_name and room_name in rooms:
            rooms[room_name].discard(user_id)
            if not rooms[room_name]:
                del rooms[room_name]
            else:
                for uid in list(rooms[room_name]):
                    if uid in connections:
                        try:
                            await connections[uid].send(json.dumps({
                                'type': 'peer_disconnected',
                                'user_id': user_id,
                            }))
                        except Exception:
                            pass


async def main():
    if not HAS_WEBSOCKETS:
        print("ERROR: websockets package not installed")
        print("Run: pip install websockets")
        return

    server = await websockets.serve(handler, '0.0.0.0', 8001)
    print("=" * 50)
    print("  Thunderbold_AI WebRTC Signaling Server")
    print("  Port: 8001")
    print("  Protocol: WebSocket (DTLS-SRTP E2E)")
    print("=" * 50)
    await server.wait_closed()


if __name__ == '__main__':
    asyncio.run(main())
