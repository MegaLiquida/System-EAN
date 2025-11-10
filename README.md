# Sistema de Gestão de Mercado

Um sistema web completo para gerenciamento de estoque, produtos e validade em pequenos mercados, desenvolvido em **Python com Flask**.

## 🎯 Funcionalidades

### Módulo de Autenticação
- ✅ Registro de novos mercados (tenants)
- ✅ Login seguro com criptografia de senha
- ✅ Gestão de usuários (Admin, Estoquista, Gerente)
- ✅ Controle de acesso por role

### Módulo de Cadastro
- ✅ Cadastro de Produtos com código de barras (GTIN)
- ✅ Cadastro de Categorias
- ✅ Cadastro de Fornecedores
- ✅ Preenchimento manual de preços (custo e venda)

### Módulo de Estoque
- ✅ Entrada de estoque (Armazém)
- ✅ Saída de estoque (Prateleira Loja) com baixa automática
- ✅ Transferência interna entre Armazém e Prateleira
- ✅ Consulta de estoque discriminado por localização
- ✅ Alerta de estoque mínimo

### Módulo de Validade
- ✅ Registro de data de validade
- ✅ Alertas visuais (Verde/Amarelo/Vermelho)
- ✅ Relatório de produtos próximos ao vencimento

### Módulo de Relatórios
- ✅ Relatório de posição de estoque com valorização
- ✅ Relatório de movimentação
- ✅ Relatório de validade

## 🛠️ Stack Tecnológico

- **Backend:** Python 3.11+ com Flask 3.1
- **Banco de Dados:** PostgreSQL
- **Frontend:** HTML5, Bootstrap 5, JavaScript
- **ORM:** SQLAlchemy 2.0
- **Servidor:** Gunicorn (Render)

## 📋 Requisitos

- Python 3.11+
- PostgreSQL 12+
- pip (gerenciador de pacotes Python)

## 🚀 Instalação Local

### 1. Clonar o repositório

```bash
git clone https://github.com/seu-usuario/mercado-gestao-system.git
cd mercado-gestao-system
```

### 2. Criar ambiente virtual

```bash
python -m venv venv

# No Windows
venv\Scripts\activate

# No macOS/Linux
source venv/bin/activate
```

### 3. Instalar dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas configurações:

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/mercado_db
FLASK_ENV=development
SECRET_KEY=sua-chave-secreta-muito-segura
```

### 5. Criar banco de dados

```bash
python
>>> from src.main import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

### 6. Executar a aplicação

```bash
python -m flask run
```

A aplicação estará disponível em `http://localhost:5000`

## 📦 Estrutura do Projeto

```
mercado-gestao-system/
├── src/
│   ├── main.py              # Aplicação principal Flask
│   ├── models.py            # Modelos de dados (SQLAlchemy)
│   ├── templates/           # Templates HTML (Jinja2)
│   │   ├── base.html
│   │   ├── login.html
│   │   ├── register.html
│   │   ├── dashboard.html
│   │   ├── products.html
│   │   ├── stock.html
│   │   └── reports.html
│   └── static/              # Arquivos estáticos
│       ├── css/
│       │   └── style.css
│       └── js/
│           └── main.js
├── requirements.txt         # Dependências Python
├── Procfile                 # Configuração para Render
├── .env.example            # Exemplo de variáveis de ambiente
├── .gitignore              # Arquivos ignorados pelo Git
└── README.md               # Este arquivo
```

## 🔐 Segurança

- Senhas criptografadas com Werkzeug
- Isolamento de dados por tenant (multi-tenant)
- Validação de entrada em todos os formulários
- Proteção CSRF (implementar em produção)
- Cookies HTTP-only

## 📊 Modelos de Dados

### Tenant (Mercado)
- ID, Nome, Email, Telefone, Endereço
- Configurações (dias de alerta de validade)

### User (Usuário)
- ID, Tenant ID, Username, Email, Senha (hash)
- Role (admin, estoquista, gerente)

### Product (Produto)
- ID, Tenant ID, Nome, GTIN, Marca
- Preço de Custo, Preço de Venda
- Categoria, Fornecedor, Estoque Mínimo

### Stock (Estoque)
- ID, Tenant ID, Produto ID
- Localização (warehouse, shelf)
- Quantidade

### StockMovement (Movimentação)
- ID, Tenant ID, Produto ID, Usuário ID
- Tipo (entry, exit, transfer)
- Quantidade, Data

### ProductExpiry (Validade)
- ID, Tenant ID, Produto ID
- Data de Validade, Quantidade
- Status (valid, warning, expired)

## 🌐 Deploy no Render

### 1. Criar conta no Render

Acesse [render.com](https://render.com) e crie uma conta.

### 2. Criar banco de dados PostgreSQL

1. Clique em "New +" → "PostgreSQL"
2. Configure:
   - **Name:** `mercado-db`
   - **Database:** `mercado_db`
   - **User:** `postgres`
3. Copie a **Internal Database URL**

### 3. Criar Web Service

1. Clique em "New +" → "Web Service"
2. Conecte seu repositório GitHub
3. Configure:
   - **Name:** `mercado-gestao-system`
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `gunicorn -w 4 -b 0.0.0.0:$PORT "src.main:app"`

### 4. Adicionar variáveis de ambiente

No painel do Web Service, vá para "Environment" e adicione:

```
DATABASE_URL=postgresql://postgres:PASSWORD@HOST:5432/mercado_db
FLASK_ENV=production
SECRET_KEY=gere-uma-string-aleatoria-muito-segura
```

### 5. Deploy

O Render iniciará o build automaticamente. Acompanhe em "Logs".

## 📝 Uso

### Primeiro Acesso

1. Acesse a aplicação
2. Clique em "Registre-se aqui"
3. Preencha os dados do mercado e do administrador
4. Faça login com suas credenciais

### Cadastrar Produto

1. Vá para "Produtos"
2. Clique em "Novo Produto"
3. Preencha os dados (nome, preço, categoria, etc.)
4. Clique em "Salvar Produto"

### Registrar Entrada de Estoque

1. Vá para "Estoque"
2. Clique na aba "Entrada de Estoque"
3. Selecione o produto, quantidade, fornecedor
4. Adicione data de validade (se aplicável)
5. Clique em "Registrar Entrada"

### Registrar Saída de Estoque

1. Vá para "Estoque"
2. Clique na aba "Saída de Estoque"
3. Selecione o produto e quantidade
4. Clique em "Registrar Saída"

### Gerar Relatórios

1. Vá para "Relatórios"
2. Selecione o tipo de relatório
3. Configure o período
4. Clique em "Gerar Relatório"

## 🐛 Troubleshooting

### Erro de conexão com banco de dados

- Verifique se o PostgreSQL está rodando
- Confirme a `DATABASE_URL` está correta
- Teste a conexão: `psql "postgresql://usuario:senha@localhost:5432/mercado_db"`

### Erro de importação de módulos

- Verifique se o ambiente virtual está ativado
- Reinstale as dependências: `pip install -r requirements.txt`

### Porta 5000 já em uso

```bash
# Usar porta diferente
python -m flask run --port 5001
```

## 📞 Suporte

Para reportar bugs ou sugerir melhorias, abra uma issue no GitHub.

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo LICENSE para mais detalhes.

## 👨‍💻 Desenvolvido por

Sistema de Gestão de Mercado - 2024
