from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, User, Sala, Patrimonio, Inventario, ItemInventario, SolicitacaoRealocacao, MensagemChat
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-12345')

# Configuração para Railway / PostgreSQL
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///patrimonio.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- Filtros Customizados ---
@app.template_filter('status_badge')
def status_badge(status):
    badges = {
        'pendente': 'secondary',
        'aprovado': 'success',
        'recusado': 'danger',
        'ativo': 'success',
        'inativo': 'warning',
        'confirmado': 'success',
        'alterado': 'info',
        'fora_de_lugar': 'warning',
        'nao_encontrado': 'danger'
    }
    return badges.get(status, 'primary')

# --- Rotas de Autenticação ---
@app.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('responsavel_dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('index'))
        flash('Usuário ou senha inválidos', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- Dashboard Admin ---
@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        return redirect(url_for('index'))
    
    stats = {
        'salas': Sala.query.count(),
        'patrimonios': Patrimonio.query.count(),
        'relocacoes_pendentes': SolicitacaoRealocacao.query.filter_by(status='pendente').count(),
        'inventarios_ativos': Inventario.query.filter_by(status='iniciado').count()
    }
    salas = Sala.query.all()
    relocacoes = SolicitacaoRealocacao.query.filter_by(status='pendente').all()
    return render_template('admin/dashboard.html', stats=stats, salas=salas, relocacoes=relocacoes)

# CRUD Salas (Exemplo Simplificado)
@app.route('/admin/salas', methods=['GET', 'POST'])
@login_required
def admin_salas():
    if current_user.role != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        nova_sala = Sala(
            nome=request.form.get('nome'),
            bloco=request.form.get('bloco'),
            descricao=request.form.get('descricao')
        )
        db.session.add(nova_sala)
        db.session.commit()
        flash('Sala cadastrada com sucesso!', 'success')
    salas = Sala.query.all()
    return render_template('admin/salas.html', salas=salas)

# CRUD Patrimonio
@app.route('/admin/patrimonios', methods=['GET', 'POST'])
@login_required
def admin_patrimonios():
    if current_user.role != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        novo_pat = Patrimonio(
            numero_patrimonio=request.form.get('numero'),
            descricao=request.form.get('descricao'),
            marca=request.form.get('marca'),
            modelo=request.form.get('modelo'),
            sala_id=request.form.get('sala_id')
        )
        db.session.add(novo_pat)
        db.session.commit()
        flash('Patrimônio cadastrado!', 'success')
    patrimonios = Patrimonio.query.all()
    salas = Sala.query.all()
    return render_template('admin/patrimonios.html', patrimonios=patrimonios, salas=salas)

# CRUD Responsáveis
@app.route('/admin/responsaveis', methods=['GET', 'POST'])
@login_required
def admin_responsaveis():
    if current_user.role != 'admin': return redirect(url_for('index'))
    if request.method == 'POST':
        novo_u = User(
            username=request.form.get('username'),
            email=request.form.get('email'),
            nome=request.form.get('nome'),
            role='responsavel'
        )
        novo_u.set_password(request.form.get('password'))
        # Vincular salas
        sala_ids = request.form.getlist('sala_ids')
        for sid in sala_ids:
            s = Sala.query.get(sid)
            if s: novo_u.salas.append(s)
        
        db.session.add(novo_u)
        db.session.commit()
        flash('Responsável cadastrado!', 'success')
    responsaveis = User.query.filter_by(role='responsavel').all()
    salas = Sala.query.all()
    return render_template('admin/responsaveis.html', responsaveis=responsaveis, salas=salas)

# Validação de Relocação
@app.route('/admin/relocacao/<int:id>/<string:acao>')
@login_required
def admin_processar_relocacao(id, acao):
    if current_user.role != 'admin': return redirect(url_for('index'))
    req = SolicitacaoRealocacao.query.get_or_404(id)
    if acao == 'aprovar':
        req.status = 'aprovado'
        req.patrimonio.sala_id = req.sala_destino_id
    else:
        req.status = 'recusado'
    db.session.commit()
    flash(f'Solicitação {acao}da com sucesso!', 'success')
    return redirect(url_for('admin_dashboard'))

# --- Dashboard Responsável ---
@app.route('/responsavel')
@login_required
def responsavel_dashboard():
    if current_user.role != 'responsavel':
        return redirect(url_for('index'))
    return render_template('responsavel/dashboard.html', salas=current_user.salas)

# Inventário Logic
@app.route('/inventario/sala/<int:sala_id>')
@login_required
def inventario_sala(sala_id):
    sala = Sala.query.get_or_404(sala_id)
    # Verificar se o usuário tem acesso à sala ou é admin
    if current_user.role != 'admin' and sala not in current_user.salas:
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))
    
    # Busca inventário em aberto ou cria um novo
    inv = Inventario.query.filter_by(sala_id=sala_id, status='iniciado').first()
    if not inv:
        inv = Inventario(sala_id=sala_id, responsavel_id=current_user.id)
        db.session.add(inv)
        db.session.commit()
    
    # Itens esperados na sala
    itens_esperados = Patrimonio.query.filter_by(sala_id=sala_id).all()
    # Itens já conferidos nesta sessão
    conferidos_ids = [item.patrimonio_id for item in ItemInventario.query.filter_by(inventario_id=inv.id).all()]
    
    return render_template('inventario.html', sala=sala, inventario=inv, itens_esperados=itens_esperados, conferidos_ids=conferidos_ids)

@app.route('/inventario/scan', methods=['POST'])
@login_required
def inventario_scan():
    numero = request.form.get('numero')
    sala_id = request.form.get('sala_id')
    inv_id = request.form.get('inventario_id')
    
    pat = Patrimonio.query.filter_by(numero_patrimonio=numero).first()
    
    if not pat:
        # Item não existe no sistema
        item_inv = ItemInventario(inventario_id=inv_id, status='nao_encontrado', observacao=f'Tag {numero} não cadastrada.')
        db.session.add(item_inv)
        db.session.commit()
        return jsonify({'status': 'not_found', 'message': 'Patrimônio não localizado no sistema.'})
    
    # Existe. Está na sala certa?
    if str(pat.sala_id) == str(sala_id):
        # Tudo certo
        # Evitar duplicados na mesma sessão
        existente = ItemInventario.query.filter_by(inventario_id=inv_id, patrimonio_id=pat.id).first()
        if not existente:
            item_inv = ItemInventario(inventario_id=inv_id, patrimonio_id=pat.id, sala_id_da_vez=sala_id, status='confirmado')
            db.session.add(item_inv)
            db.session.commit()
        return jsonify({'status': 'ok', 'message': f'Item confirmado: {pat.descricao}'})
    else:
        # Fora de lugar
        return jsonify({
            'status': 'wrong_room', 
            'pat_id': pat.id,
            'descricao': pat.descricao,
            'sala_atual': pat.sala.nome,
            'message': f'Item pertence à {pat.sala.nome}. Deseja solicitar relocação?'
        })

@app.route('/inventario/solicitar_relocacao', methods=['POST'])
@login_required
def solicitar_relocacao():
    data = request.json
    nova_sol = SolicitacaoRealocacao(
        patrimonio_id=data['pat_id'],
        sala_origem_id=data['sala_origem_id'], # A sala onde ele deveria estar (ou onde o sistema diz que está)
        sala_destino_id=data['sala_destino_id'], # A sala onde ele foi encontrado
        responsavel_id=current_user.id,
        observacao="Encontrado durante inventário."
    )
    # Marcar também no item do inventário
    item_inv = ItemInventario(
        inventario_id=data['inv_id'],
        patrimonio_id=data['pat_id'],
        sala_id_da_vez=data['sala_destino_id'],
        status='fora_de_lugar'
    )
    db.session.add(nova_sol)
    db.session.add(item_inv)
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/inventario/finalizar/<int:inv_id>')
@login_required
def finalizar_inventario(inv_id):
    inv = Inventario.query.get_or_404(inv_id)
    inv.status = 'concluido'
    inv.data_hora_fim = datetime.utcnow()
    db.session.commit()
    flash('Inventário finalizado!', 'success')
    return redirect(url_for('responsavel_dashboard'))

# --- Chat Logic ---
@app.route('/chat/<int:sala_id>', methods=['GET', 'POST'])
@login_required
def chat(sala_id):
    sala = Sala.query.get_or_404(sala_id)
    if request.method == 'POST':
        msg = MensagemChat(
            sala_id=sala_id,
            usuario_id=current_user.id,
            usuario_tipo='adm' if current_user.role == 'admin' else 'responsavel',
            texto=request.form.get('texto')
        )
        db.session.add(msg)
        db.session.commit()
        return redirect(url_for('chat', sala_id=sala_id))
    
    mensagens = MensagemChat.query.filter_by(sala_id=sala_id).order_by(MensagemChat.data_hora.asc()).all()
    return render_template('chat.html', sala=sala, mensagens=mensagens)

# API para Chat (Poll)
@app.route('/api/chat/<int:sala_id>')
@login_required
def api_chat(sala_id):
    mensagens = MensagemChat.query.filter_by(sala_id=sala_id).order_by(MensagemChat.data_hora.asc()).all()
    res = []
    for m in mensagens:
        res.append({
            'usuario': m.usuario.nome,
            'tipo': m.usuario_tipo,
            'texto': m.texto,
            'data': m.data_hora.strftime('%H:%M'),
            'meu': m.usuario_id == current_user.id
        })
    return jsonify(res)

# --- Inicialização ---
def seed():
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@patrimonio.com', nome='Administrador', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        
        s1 = Sala(nome='Auditório Principal', bloco='A', descricao='Espaço para eventos')
        s2 = Sala(nome='Laboratório 101', bloco='B', descricao='Laboratório de informática')
        db.session.add_all([s1, s2])
        db.session.commit()
        print("Seed finalizado: Admin (admin/admin123) criado.")

# Criar tabelas automaticamente se não existirem
with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
