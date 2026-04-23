from rest_framework import serializers
from django.contrib.auth.models import User
from .models import PerfilUsuario, Conversa, Mensagem
import json


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'date_joined']


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    usuario = UserSerializer(read_only=True)
    
    class Meta:
        model = PerfilUsuario
        fields = ['id', 'usuario', 'criado_em', 'atualizado_em']
        read_only_fields = ['rsa_public_key', 'elgamal_public_key', 'ecc_public_key']


class ConversaSerializer(serializers.ModelSerializer):
    remetente_username = serializers.CharField(source='remetente.username', read_only=True)
    destinatario_username = serializers.CharField(source='destinatario.username', read_only=True)
    total_mensagens = serializers.SerializerMethodField()
    
    class Meta:
        model = Conversa
        fields = [
            'id', 'remetente', 'destinatario', 'remetente_username', 'destinatario_username',
            'algoritmo_escolhido', 'ativa', 'dh_completo', 'criado_em', 
            'ultima_atividade', 'total_mensagens'
        ]
        read_only_fields = ['id', 'criado_em', 'ultima_atividade']
    
    def get_total_mensagens(self, obj):
        return obj.mensagens.count()


class MensagemSerializer(serializers.ModelSerializer):
    remetente_username = serializers.CharField(source='remetente.username', read_only=True)
    conteudo_decifrado = serializers.SerializerMethodField()
    
    class Meta:
        model = Mensagem
        fields = [
            'id', 'conversa', 'remetente', 'remetente_username',
            'tipo', 'algoritmo', 'hash_algoritmo',
            'conteudo_decifrado', 'integridade_ok', 'assinatura_verificada',
            'enviado_em', 'recebido_em', 'lido'
        ]
        read_only_fields = ['id', 'enviado_em']
    
    def get_conteudo_decifrado(self, obj):
        """Tenta decifrar se disponível no contexto"""
        if hasattr(obj, '_conteudo_decifrado'):
            return obj._conteudo_decifrado
        return None


class MensagemCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mensagem
        fields = ['conversa', 'tipo', 'algoritmo', 'conteudo_cifrado', 
                 'hash_algoritmo', 'hash_original', 'assinatura', 'nonce']