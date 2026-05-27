# Secure Messaging API

API segura para mensagens criptografadas construída com Django REST Framework.

## Funcionalidades

- 🔐 Autenticação com Token
- 🎯 Criptografia de ponta a ponta
- 💬 Mensagens privadas
- 👥 Sistema de amizades
- 📱 Notificações em tempo real
- 👑 Painel administrativo

## Deploy no Render

### Configuração automática

1. Conecte seu repositório ao Render
2. O arquivo `render.yaml` será detectado automaticamente
3. O banco de dados PostgreSQL será criado
4. O build será executado com `build.sh`

### Variáveis de ambiente necessárias

- `SECRET_KEY`: Gerada automaticamente
- `DATABASE_URL`: Configurada automaticamente
- `DEBUG`: false
- `ALLOWED_HOSTS`: .onrender.com

### Criar superusuário

Após o deploy, acesse o shell do Render:
```bash
python manage.py createsuperuser