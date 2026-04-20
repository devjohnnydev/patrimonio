from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Escola, User, Sala, Patrimonio, Inventario, ItemInventario, SolicitacaoRealocacao, MensagemChat
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

# --- Auxiliares e Mock de E-mail ---
def mock_enviar_email(destinatario, assunto, corpo):
    print("\n--- [SIMULAÇÃO DE E-MAIL] ---")
    print(f"PARA: {destinatario}")
    print(f"ASSUNTO: {assunto}")
    print(f"MENSAGEM: {corpo}")
    print("-----------------------------\n")

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
        'nao_encontrado': 'danger',
        'concluido': 'primary',
        'validado': 'dark'
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
    
    # Filtro por escola
    e_id = current_user.escola_id
    stats = {
        'salas': Sala.query.filter_by(escola_id=e_id).count(),
        'patrimonios': Patrimonio.query.filter_by(escola_id=e_id).count(),
        'quebrados': Patrimonio.query.filter_by(escola_id=e_id, status_conservacao='quebrado').count(),
        'relocacoes_pendentes': SolicitacaoRealocacao.query.filter_by(escola_id=e_id, status='pendente').count()
    }
    salas = Sala.query.filter_by(escola_id=e_id).all()
    relocacoes = SolicitacaoRealocacao.query.filter_by(escola_id=e_id, status='pendente').all()
    quebrados = Patrimonio.query.filter_by(escola_id=e_id, status_conservacao='quebrado').all()
    
    return render_template('admin/dashboard.html', stats=stats, salas=salas, relocacoes=relocacoes, quebrados=quebrados)

# CRUD Salas
@app.route('/admin/salas', methods=['GET', 'POST'])
@login_required
def admin_salas():
    if current_user.role != 'admin': return redirect(url_for('index'))
    e_id = current_user.escola_id
    if request.method == 'POST':
        nova_sala = Sala(
            nome=request.form.get('nome'),
            bloco=request.form.get('bloco'),
            descricao=request.form.get('descricao'),
            escola_id=e_id
        )
        db.session.add(nova_sala)
        db.session.commit()
        flash('Sala cadastrada!', 'success')
    salas = Sala.query.filter_by(escola_id=e_id).all()
    return render_template('admin/salas.html', salas=salas)

# CRUD Patrimonio
@app.route('/admin/patrimonios', methods=['GET', 'POST'])
@login_required
def admin_patrimonios():
    if current_user.role != 'admin': return redirect(url_for('index'))
    e_id = current_user.escola_id
    if request.method == 'POST':
        novo_pat = Patrimonio(
            numero_patrimonio=request.form.get('numero'),
            descricao=request.form.get('descricao'),
            marca=request.form.get('marca'),
            modelo=request.form.get('modelo'),
            sala_id=request.form.get('sala_id'),
            imagem_url=request.form.get('imagem_url'),
            escola_id=e_id
        )
        db.session.add(novo_pat)
        db.session.commit()
    patrimonios = Patrimonio.query.filter_by(escola_id=e_id).all()
    salas = Sala.query.filter_by(escola_id=e_id).all()
    return render_template('admin/patrimonios.html', patrimonios=patrimonios, salas=salas)

# Fluxo de Descarte
@app.route('/admin/descartar/<int:id>')
@login_required
def admin_descartar(id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    pat = Patrimonio.query.filter_by(id=id, escola_id=current_user.escola_id).first_or_404()
    pat.status = 'descartado'
    pat.status_conservacao = 'descartado'
    db.session.commit()
    flash('Item enviado para descarte!', 'success')
    return redirect(url_for('admin_dashboard'))

# Conferência de Inventário (Conflitos)
@app.route('/admin/conferir/<int:inv_id>')
@login_required
def admin_conferir_inventario(inv_id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    inv = Inventario.query.filter_by(id=inv_id, escola_id=current_user.escola_id).first_or_404()
    
    # Itens esperados na sala
    esperados = Patrimonio.query.filter_by(sala_id=inv.sala_id, status='ativo').all()
    # Itens registrados no inventario
    registrados = ItemInventario.query.filter_by(inventario_id=inv.id).all()
    registrados_ids = [r.patrimonio_id for r in registrados if r.patrimonio_id]
    
    # Detectar Faltantes
    faltantes = []
    for p in esperados:
        if p.id not in registrados_ids:
            faltantes.append(p)
            
    # Detectar Extras/Fora de Lugar (Já registrados no ItemInventario)
    extras = [r for r in registrados if r.status in ['fora_de_lugar', 'nao_encontrado']]
    
    return render_template('admin/conferir_inventario.html', inv=inv, esperados=esperados, registrados=registrados, faltantes=faltantes, extras=extras)

@app.route('/admin/validar_inventario/<int:inv_id>')
@login_required
def admin_validar_inventario(inv_id):
    if current_user.role != 'admin': return redirect(url_for('index'))
    inv = Inventario.query.filter_by(id=inv_id, escola_id=current_user.escola_id).first_or_404()
    inv.status = 'validado'
    db.session.commit()
    flash('Inventário validado e arquivado!', 'success')
    return redirect(url_for('admin_dashboard'))

# CRUD Responsáveis (Com Notificação)
@app.route('/admin/responsaveis', methods=['GET', 'POST'])
@login_required
def admin_responsaveis():
    if current_user.role != 'admin': return redirect(url_for('index'))
    e_id = current_user.escola_id
    if request.method == 'POST':
        senha_pura = request.form.get('password')
        novo_u = User(
            username=request.form.get('username'),
            email=request.form.get('email'),
            nome=request.form.get('nome'),
            role='responsavel',
            escola_id=e_id
        )
        novo_u.set_password(senha_pura)
        
        # Enviar Notificação
        mock_enviar_email(
            novo_u.email, 
            f"Seu Acesso ao Sistema SENAI - {current_user.escola.nome}",
            f"Olá {novo_u.nome}, seu acesso foi criado.\nUsuário: {novo_u.username}\nSenha: {senha_pura}\nUnidade: {current_user.escola.nome}"
        )
        
        sala_ids = request.form.getlist('sala_ids')
        for sid in sala_ids:
            s = Sala.query.filter_by(id=sid, escola_id=e_id).first()
            if s: novo_u.salas.append(s)
        db.session.add(novo_u)
        db.session.commit()

# Validação de Relocação
@app.route('/admin/relocacao/<int:id>/<string:acao>')
@login_required
def admin_processar_relocacao(id, acao):
    if current_user.role != 'admin': return redirect(url_for('index'))
    req = SolicitacaoRealocacao.query.filter_by(id=id, escola_id=current_user.escola_id).first_or_404()
    if acao == 'aprovar':
        req.status = 'aprovado'
        req.patrimonio.sala_id = req.sala_destino_id
    else:
        req.status = 'recusado'
    db.session.commit()
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
    sala = Sala.query.filter_by(id=sala_id, escola_id=current_user.escola_id).first_or_404()
    if current_user.role != 'admin' and sala not in current_user.salas:
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))
    
    inv = Inventario.query.filter_by(sala_id=sala_id, status='iniciado', escola_id=current_user.escola_id).first()
    if not inv:
        inv = Inventario(sala_id=sala_id, responsavel_id=current_user.id, escola_id=current_user.escola_id)
        db.session.add(inv)
        db.session.commit()
    
    itens_esperados = Patrimonio.query.filter_by(sala_id=sala_id, status='ativo').all()
    conferidos_ids = [item.patrimonio_id for item in ItemInventario.query.filter_by(inventario_id=inv.id).all()]
    
    return render_template('inventario.html', sala=sala, inventario=inv, itens_esperados=itens_esperados, conferidos_ids=conferidos_ids)

@app.route('/inventario/scan', methods=['POST'])
@login_required
def inventario_scan():
    numero = request.form.get('numero')
    sala_id = request.form.get('sala_id')
    inv_id = request.form.get('inventario_id')
    e_id = current_user.escola_id
    
    pat = Patrimonio.query.filter_by(numero_patrimonio=numero, escola_id=e_id).first()
    
    if not pat:
        item_inv = ItemInventario(inventario_id=inv_id, status='nao_encontrado', observacao=f'Tag {numero} não cadastrada.')
        db.session.add(item_inv)
        db.session.commit()
        return jsonify({'status': 'not_found', 'message': 'Patrimônio não localizado no sistema.'})
    
    if str(pat.sala_id) == str(sala_id):
        existente = ItemInventario.query.filter_by(inventario_id=inv_id, patrimonio_id=pat.id).first()
        if not existente:
            item_inv = ItemInventario(inventario_id=inv_id, patrimonio_id=pat.id, sala_id_da_vez=sala_id, status='confirmado')
            db.session.add(item_inv)
            db.session.commit()
        return jsonify({'status': 'ok', 'message': f'Item confirmado: {pat.descricao}', 'imagem': pat.imagem_url})
    else:
        return jsonify({
            'status': 'wrong_room', 
            'pat_id': pat.id,
            'descricao': pat.descricao,
            'sala_atual': pat.sala.nome,
            'imagem': pat.imagem_url,
            'message': f'Item pertence à {pat.sala.nome}. Deseja solicitar relocação?'
        })

@app.route('/inventario/marcar_quebrado', methods=['POST'])
@login_required
def marcar_quebrado():
    data = request.json
    pat = Patrimonio.query.filter_by(id=data['pat_id'], escola_id=current_user.escola_id).first_or_404()
    pat.status_conservacao = 'quebrado'
    db.session.commit()
    return jsonify({'status': 'success'})

@app.route('/inventario/solicitar_relocacao', methods=['POST'])
@login_required
def solicitar_relocacao():
    data = request.json
    nova_sol = SolicitacaoRealocacao(
        patrimonio_id=data['pat_id'],
        sala_origem_id=data['sala_origem_id'] if data.get('sala_origem_id') else Patrimonio.query.get(data['pat_id']).sala_id,
        sala_destino_id=data['sala_destino_id'],
        responsavel_id=current_user.id,
        escola_id=current_user.escola_id,
        observacao="Encontrado durante inventário."
    )
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
    if not Escola.query.first():
        # Escola 1: SENAI São Paulo - Unidade Ipiranga
        e1 = Escola(nome='SENAI Ipiranga', codigo_senai='1.01', cidade='São Paulo')
        # Escola 2: SENAI São Paulo - Unidade Vila Mariana
        e2 = Escola(nome='SENAI Vila Mariana', codigo_senai='1.02', cidade='São Paulo')
        db.session.add_all([e1, e2])
        db.session.commit()

        # Admin Escola 1
        admin = User(username='admin', email='admin@senai.br', nome='Admin SENAI', role='admin', escola_id=e1.id)
        admin.set_password('admin123')
        
        # Responsável Escola 1
        resp = User(username='joao', email='joao@senai.br', nome='João Silva', role='responsavel', escola_id=e1.id)
        resp.set_password('joao123')
        
        db.session.add_all([admin, resp])
        
        # Salas Escola 1
        s1 = Sala(nome='Oficina de Automobilística', bloco='A', descricao='Oficina principal', escola_id=e1.id)
        s2 = Sala(nome='Laboratório de Metrologia', bloco='B', descricao='Lab de medição', escola_id=e1.id)
        db.session.add_all([s1, s2])
        db.session.commit()
        
        # Vincular João à Oficina
        resp.salas.append(s1)

        # Patrimônios Escola 1 (Links de imagem de exemplo)
        p1 = Patrimonio(
            numero_patrimonio='984640',
            descricao='JOGO CALIBRADORES DE ROSCA/COSA',
            marca='Mitutoyo',
            modelo='H-21',
            imagem_url='https://images.unsplash.com/photo-1541013726909-002d99d3e55c?q=80&w=200&auto=format&fit=crop',
            sala_id=s2.id,
            escola_id=e1.id
        )
        p2 = Patrimonio(
            numero_patrimonio='1175858',
            descricao='CADEIRA FIXA POLIPROPILENO AZUL',
            marca='Plaxmetal',
            modelo='Linha Office',
            imagem_url='https://images.unsplash.com/photo-1592074522340-025515c0e7ed?q=80&w=200&auto=format&fit=crop',
            sala_id=s1.id,
            escola_id=e1.id
        )
        db.session.add_all([p1, p2])
        db.session.commit()
        print("Seed SaaS finalizado.")

# Criar tabelas e rodar seed
with app.app_context():
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
