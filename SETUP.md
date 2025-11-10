# Guia de Configuração - Render

Este guia descreve como configurar e fazer deploy do **Sistema de Gestão de Mercado** no Render.

## 📋 Pré-requisitos

- Conta no GitHub
- Conta no Render
- Repositório do projeto no GitHub

## 🚀 Passo a Passo

### 1. Preparar o Repositório GitHub

```bash
# Clonar o projeto
git clone https://github.com/seu-usuario/mercado-gestao-system.git
cd mercado-gestao-system

# Fazer push para seu repositório
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Criar Banco de Dados PostgreSQL no Render

1. Acesse [render.com](https://render.com)
2. Clique em **"New +"** no canto superior direito
3. Selecione **"PostgreSQL"**
4. Preencha os dados:
   - **Name:** `mercado-db`
   - **Database:** `mercado_db`
   - **User:** `postgres`
   - **Region:** Escolha a mais próxima
   - **PostgreSQL Version:** 15
5. Clique em **"Create Database"**
6. **Copie a "Internal Database URL"** (será usada como `DATABASE_URL`)

### 3. Criar Web Service no Render

1. Clique em **"New +"** novamente
2. Selecione **"Web Service"**
3. Conecte seu repositório GitHub
4. Preencha os dados:
   - **Name:** `mercado-gestao-system`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 4 -b 0.0.0.0:$PORT "src.main:app"`
   - **Instance Type:** `Standard` (ou `Starter` para testes)

### 4. Configurar Variáveis de Ambiente

Após criar o Web Service:

1. Vá para a aba **"Environment"**
2. Adicione as seguintes variáveis:

```
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:5432/mercado_db
FLASK_ENV=production
SECRET_KEY=gere-uma-string-aleatoria-muito-segura-aqui
```

**Onde:**
- `PASSWORD`: Senha do banco de dados (fornecida pelo Render)
- `HOST`: Host do banco de dados (fornecido pelo Render)
- `SECRET_KEY`: Gere uma string aleatória segura (use um gerador online)

### 5. Monitorar o Deploy

1. Após adicionar as variáveis, o Render iniciará o build automaticamente
2. Acompanhe o progresso na aba **"Logs"**
3. Quando o status mudar para **"Live"**, o deploy foi bem-sucedido

### 6. Acessar a Aplicação

- URL: `https://seu-servico.onrender.com`
- Faça login ou registre um novo mercado

## 🔧 Configuração Avançada

### Aumentar Timeout de Build

Se o build falhar por timeout:

1. Vá para **"Settings"**
2. Procure por **"Build Command"**
3. Aumente o timeout se necessário

### Usar Variáveis de Ambiente Seguras

Para gerar uma `SECRET_KEY` segura:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Conectar ao Banco de Dados Diretamente

Para debug, você pode conectar ao banco usando:

```bash
psql "postgresql://postgres:PASSWORD@HOST:5432/mercado_db"
```

## 📊 Monitoramento

### Logs

- Acesse a aba **"Logs"** para ver logs em tempo real
- Procure por erros ou avisos

### Métricas

- Clique em **"Metrics"** para ver uso de CPU, memória e rede

### Alertas

Configure alertas para:
- Falha de deploy
- Erro na aplicação
- Alto uso de recursos

## 🐛 Troubleshooting

### Erro: "Connection refused"

**Causa:** Banco de dados não está acessível

**Solução:**
1. Verifique se o banco de dados foi criado com sucesso
2. Confirme que `DATABASE_URL` está correta
3. Aguarde alguns minutos para o banco ficar pronto

### Erro: "ModuleNotFoundError"

**Causa:** Dependências não foram instaladas

**Solução:**
1. Verifique se `requirements.txt` está no repositório
2. Verifique o Build Command: `pip install -r requirements.txt`
3. Recrie o Web Service

### Erro: "SECRET_KEY not set"

**Causa:** Variável de ambiente não foi configurada

**Solução:**
1. Vá para **"Environment"**
2. Adicione `SECRET_KEY` com um valor seguro
3. Clique em **"Deploy"** para reiniciar

### Aplicação lenta

**Solução:**
1. Aumente o número de workers em Start Command: `gunicorn -w 8 ...`
2. Upgrade para instance type maior
3. Otimize queries do banco de dados

## 🔄 Atualizações

Para fazer deploy de uma nova versão:

1. Faça as alterações no código
2. Commit e push para GitHub:
   ```bash
   git add .
   git commit -m "Descrição das mudanças"
   git push origin main
   ```
3. O Render detectará as mudanças e iniciará o deploy automaticamente

Para forçar um redeploy:

1. Vá para o Web Service
2. Clique em **"Manual Deploy"** → **"Deploy latest commit"**

## 💾 Backup do Banco de Dados

Para fazer backup do PostgreSQL no Render:

1. Acesse o banco de dados
2. Use a ferramenta de backup do Render
3. Ou use `pg_dump`:
   ```bash
   pg_dump "postgresql://postgres:PASSWORD@HOST:5432/mercado_db" > backup.sql
   ```

## 📞 Suporte

- [Documentação do Render](https://render.com/docs)
- [Documentação do Flask](https://flask.palletsprojects.com)
- [Documentação do PostgreSQL](https://www.postgresql.org/docs)

---

**Parabéns!** Seu Sistema de Gestão de Mercado está no ar! 🎉
