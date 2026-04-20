# Sistema de Controle de Inventário de Patrimônio

Um sistema web moderno para controle de patrimônio por sala, desenvolvido com Python, Flask e SQLAlchemy.

## 🚀 Funcionalidades

- **Múltiplos Perfis:** Administrador e Responsável por Sala.
- **Gestão de Salas:** Cadastro, edição e listagem de ambientes.
- **Gestão de Patrimônio:** Controle de itens tombados com vinculação a salas.
- **Inventário por Sala:** Processo de contagem com validação inteligente.
- **Solicitações de Relocação:** Detecção automática de itens fora de lugar e fluxo de aprovação pelo admin.
- **Chat Integrado:** Comunicação direta por sala entre responsáveis e administradores.
- **Premium UI:** Interface escura, responsiva e com alta usabilidade (Bootstrap 5).

## 🛠️ Tecnologias Utilizadas

- **Backend:** Python 3 + Flask
- **Banco de Dados:** SQLAlchemy (SQLite)
- **Frontend:** Jinja2, Bootstrap 5, AJAX/Polling
- **Autenticação:** Flask-Login

## 📦 Como Instalar e Executar

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/devjohnnydev/patrimonio.git
   cd patrimonio
   ```

2. **Crie e ative um ambiente virtual (opcional):**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows
   ```

3. **Instale as dependências:**
   ```bash
   pip install Flask Flask-SQLAlchemy Flask-Login
   ```

4. **Inicialize o Banco de Dados:**
   ```bash
   python init_db.py
   ```

5. **Execute a aplicação:**
   ```bash
   python app.py
   ```

6. **Acesse no navegador:**
   `http://127.0.0.1:5000`

## 🔑 Credenciais Iniciais

- **Administrador:** `admin` / `admin123`

---

Desenvolvido para gestão eficiente de ativos organizacionais.
