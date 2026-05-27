#!/bin/bash
set -e

echo "========================================="
echo "🚀 HAREMESSENGER - DEPLOY NO RENDER"
echo "========================================="

echo ""
echo "📦 Instalando dependências Python..."
pip install -r requirements.txt

echo ""
echo "📁 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo ""
echo "🗄️ Executando migrações do banco de dados..."
python manage.py migrate --noinput

echo ""
echo "👤 Criando superusuário (se configurado)..."
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    python manage.py createsuperuser --noinput --username $DJANGO_SUPERUSER_USERNAME --email ${DJANGO_SUPERUSER_EMAIL:-admin@example.com} || true
    echo "✅ Superusuário criado/verificado"
fi

echo ""
echo "========================================="
echo "✅ BUILD CONCLUÍDO COM SUCESSO!"
echo "📍 API disponível em: /api/"
echo "📍 Admin disponível em: /admin/"
echo "========================================="