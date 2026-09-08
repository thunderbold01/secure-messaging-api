import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from rest_framework.authtoken.models import Token


connected_users = {}


class CallConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer - signaling WebRTC entre utilizadores"""

    async def connect(self):
        self.user = None
        self.my_channel = None

        token_key = self.scope.get('query_string', b'').decode()
        if 'token=' in token_key:
            token_key = token_key.split('token=')[1].split('&')[0]
            self.user = await self.get_user_from_token(token_key)

        if self.user:
            await self.accept()
            self.my_channel = f'user_{self.user.id}'
            connected_users[self.user.id] = self.channel_name
            await self.channel_layer.group_add(self.my_channel, self.channel_name)
            await self.send(text_data=json.dumps({'type': 'connected', 'user_id': self.user.id}))
            print(f'[WS] User {self.user.id} ({self.user.username}) connected. Total: {len(connected_users)}')
        else:
            await self.close()

    async def disconnect(self, close_code):
        if self.user and self.my_channel:
            connected_users.pop(self.user.id, None)
            await self.channel_layer.group_discard(self.my_channel, self.channel_name)
            print(f'[WS] User {self.user.id} disconnected. Total: {len(connected_users)}')

    async def receive(self, text_data):
        data = json.loads(text_data)
        msg_type = data.get('type')
        target_id = data.get('target_user_id')

        if not target_id:
            return

        if msg_type in ('call_offer', 'call_answer', 'ice_candidate', 'call_reject', 'call_end'):
            target_channel = f'user_{target_id}'
            await self.channel_layer.group_send(target_channel, {
                'type': 'forward_signal',
                'signal_type': msg_type,
                'sender_id': self.user.id,
                'sender_name': self.user.username,
                'data': data,
            })
            print(f'[WS] {msg_type} from {self.user.id} -> {target_id}')

        elif msg_type == 'call_request':
            target_channel = f'user_{target_id}'
            await self.channel_layer.group_send(target_channel, {
                'type': 'incoming_call',
                'sender_id': self.user.id,
                'sender_name': self.user.username,
                'call_type': data.get('call_type', 'voice'),
            })
            await self.send(text_data=json.dumps({'type': 'call_sent'}))
            print(f'[WS] call_request from {self.user.id} -> {target_id}')

    async def forward_signal(self, event):
        if self.user and event['sender_id'] == self.user.id:
            return
        await self.send(text_data=json.dumps({
            'type': event['signal_type'],
            'sender_id': event['sender_id'],
            'sender_name': event.get('sender_name', ''),
            **event['data'],
        }))

    async def incoming_call(self, event):
        if event['sender_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'incoming_call',
                'sender_id': event['sender_id'],
                'sender_name': event['sender_name'],
                'call_type': event.get('call_type', 'voice'),
            }))

    @database_sync_to_async
    def get_user_from_token(self, key):
        try:
            token = Token.objects.select_related('user').get(key=key)
            return token.user
        except Token.DoesNotExist:
            return None
