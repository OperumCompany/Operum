# Deploy da Operum na VPS Hostinger

Este guia publica a Operum em `https://operum.ktrixtech.com.br` usando Docker Compose na VPS. A VPS roda Nginx, frontend, API, worker e Redis. Supabase e DeepSeek ficam fora da VPS.

## 1. Preparar DNS

No provedor DNS do domínio `ktrixtech.com.br`, crie:

```text
Tipo: A
Nome: operum
Valor: IP_DA_VPS
TTL: padrão
```

Aguarde a propagação antes de emitir o certificado.

## 2. Preparar VPS Ubuntu 24.04

Conecte por SSH e instale Docker:

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

Crie a pasta de produção:

```bash
sudo mkdir -p /opt/operum
sudo chown -R "$USER":"$USER" /opt/operum
```

## 3. Clonar o projeto

```bash
cd /opt
git clone git@github.com:OperumCompany/Operum.git operum
cd /opt/operum
```

Se usar HTTPS em vez de SSH:

```bash
git clone https://github.com/OperumCompany/Operum.git operum
```

## 4. Criar variáveis de produção

```bash
cp .env.production.example .env.production
nano .env.production
```

Preencha os valores reais de Supabase, DeepSeek, BRAPI e `OPERUM_REFRESH_TOKEN`. Não commite `.env.production`.

O Docker de produção usa `requirements.prod.txt`, que evita baixar pacotes locais pesados de LLM/embeddings como `torch`, `transformers` e `sentence-transformers`, e usa `xgboost-cpu` para não puxar dependências CUDA. Isso combina com a configuração de produção usando DeepSeek externo e `NEWS_EMBEDDINGS_ENABLED=false`.

Para DeepSeek:

```text
AI_PROVIDER=deepseek
AI_BASE_URL=https://api.deepseek.com
AI_MODEL=deepseek-flash
AI_API_KEY=sua_chave_deepseek
```

## 5. Subir a aplicação

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Verifique:

```bash
docker compose -f docker-compose.prod.yml ps
curl -k https://operum.ktrixtech.com.br/api/health
```

Na primeira subida, o Nginx usa um certificado temporário autoassinado apenas para conseguir iniciar antes do Let's Encrypt.

## 6. Emitir SSL Let's Encrypt

Depois que o DNS apontar corretamente para a VPS:

```bash
docker compose -f docker-compose.prod.yml run --rm \
  --entrypoint certbot nginx certonly \
  --webroot \
  --webroot-path /var/www/certbot \
  --email seu-email@dominio.com \
  --agree-tos \
  --no-eff-email \
  -d operum.ktrixtech.com.br
```

Recarregue o Nginx:

```bash
docker compose -f docker-compose.prod.yml restart nginx
```

Teste sem `-k`:

```bash
curl https://operum.ktrixtech.com.br/api/health
```

## 7. Renovação do certificado

Crie um cron no host:

```bash
sudo crontab -e
```

Adicione:

```cron
0 3 * * * cd /opt/operum && docker compose -f docker-compose.prod.yml run --rm --entrypoint certbot nginx renew --webroot --webroot-path /var/www/certbot && docker compose -f docker-compose.prod.yml restart nginx
```

## 8. Atualizações

Para publicar uma nova versão:

```bash
cd /opt/operum
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

## 9. GitHub Actions

Após o deploy, configure secrets no GitHub:

```text
OPERUM_REFRESH_URL=https://operum.ktrixtech.com.br/api/news/reindex
OPERUM_REFRESH_TOKEN=mesmo_valor_do_backend
```

Isso permite que o workflow agendado de notícias execute sem o aviso "No jobs were run".
