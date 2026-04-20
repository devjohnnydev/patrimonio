# 🛡️ SaaS Patrimônio SENAI - Gestão de Alta Performance

Um ecossistema digital robusto projetado para o controle total, auditoria e rastreabilidade de ativos patrimoniais em unidades educacionais. Focado em acurácia, transparência e agilidade na tomada de decisão.

## 🚀 Funcionalidades Master

### 📊 Radar de Auditoria Master
- **Eficiência Global:** Medidor em tempo real da integridade patrimonial de toda a unidade.
- **Ranking de Intervenção:** Algoritmo que identifica automaticamente as 5 salas com menor acurácia para ação imediata da coordenação.
- **Monitoramento de Perdas:** Feed constante de itens não localizados recentemente durante os ciclos de balanço.

### 🔔 Sistema de Notificações Ativa
- **Sininho Inteligente:** Ícone com contador de mensagens não lidas integrado à barra lateral.
- **Central de Avisos:** Página centralizada para gestão de alertas e comunicações por ambiente.
- **Leitura Automática:** Sistema que sincroniza o status de visualização ao entrar em chats específicos.

### 👨‍🏫 Portal do Professor (Dashboard Avançado)
- **Métricas de Acurácia (0-100%):** Barra de progresso visual baseada em conferência física.
- **Filtros de Auditoria:** Contagem detalhada de itens **Faltantes**, **Em Conflito** (fora do lugar) e **Danificados**.
- **Timeline de Auditoria:** Rastreamento da última contagem realizada e exibição de prazos (Deadlines) para entrega do balanço.

### 🔍 Auditoria Detalhada por Ambiente
- **X-Ray de Sala:** Visão granular para o Admin Master sobre cada item, permitindo ver quem validou, quando e qual o status individual do bem.
- **Gestão de Responsáveis:** Visualização rápida de todos os professores vinculados ao ambiente com fotos e contatos.

### ☁️ Infraestrutura SaaS & Estabilidade
- **Multi-tenant:** Isolamento completo de dados por unidade escolar (`escola_id`).
- **Migrações Automáticas:** Sistema de "Startup Migration" que garante a integridade do esquema PostgreSQL no Railway a cada deploy.
- **Persistência Híbrida:** Suporte a fotos de perfil e patrimônio com fallback automático para garantir 100% de disponibilidade visual.

## 🛠️ Tecnologias Utilizadas

- **Core:** Python 3.11+ / Flask / SQLAlchemy 2.0 (PostgreSQL / SQLite)
- **Segurança:** Flask-Login / Werkzeug Security (Hashing)
- **Frontend Premium:** Bootstrap 5 / Bi-Icons / CSS3 Flexbox para dashboards responsivos
- **Integração:** Ripgrep para buscas / Git para controle de versão

## 📦 Como Instalar e Executar

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/devjohnnydev/patrimonio.git
   cd patrimonio
   ```

2. **Configure o ambiente:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # venv\Scripts\activate no Windows
   pip install -r requirements.txt
   ```

3. **Inicie o sistema:**
   ```bash
   python app.py
   ```

4. **Acesse:** `http://localhost:5000`

## 🔑 Credenciais Master
- **Usuário:** `admin`
- **Senha:** `admin123`

---

**Desenvolvido para transformar o inventário físico em inteligência estratégica.** 🏁🏆🛡️📈
