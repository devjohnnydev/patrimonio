from flask import Flask, render_template, redirect, url_for, request, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from models import db, Escola, User, Sala, Patrimonio, Inventario, ItemInventario, SolicitacaoRealocacao, MensagemChat
from datetime import datetime
import os
import openpyxl
from sqlalchemy import func

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
        if current_user.role in ['admin', 'coordenador']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('professor_dashboard'))
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
    if current_user.role not in ['admin', 'coordenador']:
        return redirect(url_for('index'))
    
    e_id = current_user.escola_id
    
    # Métricas Avançadas
    stats = {
        'salas': Sala.query.filter_by(escola_id=e_id).count(),
        'patrimonios': Patrimonio.query.filter_by(escola_id=e_id).count(),
        'quebrados': Patrimonio.query.filter_by(escola_id=e_id, status_conservacao='quebrado').count(),
        'relocacoes_pendentes': SolicitacaoRealocacao.query.filter_by(escola_id=e_id, status='pendente').count()
    }
    
    # Quantidade por Sala
    itens_por_sala = db.session.query(Sala.nome, func.count(Patrimonio.id)).\
        join(Patrimonio, Patrimonio.sala_id == Sala.id).\
        filter(Sala.escola_id == e_id).\
        group_by(Sala.nome).all()

    # Status de Conservação
    conservacao_stats = db.session.query(Patrimonio.status_conservacao, func.count(Patrimonio.id)).\
        filter(Patrimonio.escola_id == e_id).\
        group_by(Patrimonio.status_conservacao).all()

    # Produtividade por Responsável
    produtividade = db.session.query(User.nome, func.count(Inventario.id)).\
        join(Inventario, Inventario.responsavel_id == User.id).\
        filter(User.escola_id == e_id).\
        group_by(User.nome).all()

    salas = Sala.query.filter_by(escola_id=e_id).all()
    relocacoes = SolicitacaoRealocacao.query.filter_by(escola_id=e_id, status='pendente').all()
    quebrados = Patrimonio.query.filter_by(escola_id=e_id, status_conservacao='quebrado').all()
    inventarios_concluidos = Inventario.query.filter_by(escola_id=e_id, status='concluido').all()
    
    return render_template('admin/dashboard.html', 
                           stats=stats, 
                           salas=salas, 
                           relocacoes=relocacoes, 
                           quebrados=quebrados,
                           itens_por_sala=itens_por_sala,
                           conservacao_stats=conservacao_stats,
                           produtividade=produtividade,
                           inventarios_concluidos=inventarios_concluidos)

@app.route('/sala/exportar/<int:sala_id>')
@login_required
def exportar_sala_excel(sala_id):
    sala = Sala.query.get_or_404(sala_id)
    # Segurança: Verificar se pertence à escola
    if sala.escola_id != current_user.escola_id:
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))
    
    # Segurança: Se for responsável, verificar se a sala é dele
    if current_user.role == 'responsavel' and sala not in current_user.salas:
        flash('Acesso negado!', 'danger')
        return redirect(url_for('index'))

    from io import BytesIO
    from flask import send_file

    wb = openpyxl.Workbook()
    sheet = wb.active
    sheet.title = "Patrimonios"
    
    headers = ["Patrimonio", "Descricao", "Marca", "Modelo", "Status Conservacao"]
    sheet.append(headers)
    
    patrimonios = Patrimonio.query.filter_by(sala_id=sala_id, status='ativo').all()
    for p in patrimonios:
        sheet.append([p.numero_patrimonio, p.descricao, p.marca, p.modelo, p.status_conservacao])
    
    output = BytesIO()
    wb.save(output)
    output.seek(0)
    
    filename = f"patrimonio_sala_{sala.nome.replace(' ', '_')}.xlsx"
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@app.route('/admin/importar', methods=['POST'])
@login_required
def admin_importar_excel():
    if current_user.role != 'admin': return redirect(url_for('index'))
    if 'file' not in request.files:
        flash('Nenhum arquivo enviado', 'danger')
        return redirect(url_for('admin_patrimonios'))
    
    file = request.files['file']
    if file.filename == '':
        flash('Nenhum arquivo selecionado', 'danger')
        return redirect(url_for('admin_patrimonios'))

    try:
        wb = openpyxl.load_workbook(file)
        sheet = wb.active
        e_id = current_user.escola_id
        count = 0
        
        # Mapeamento de colunas (Ignora a primeira linha de cabeçalho)
        # Assume: A: Patrimonio, B: Descricao, C: Marca, D: Modelo, E: Sala, F: Foto
        # Ou busca pelo nome na primeira linha
        headers = [str(cell.value).strip() if cell.value else "" for cell in sheet[1]]
        
        def get_val(row, col_name):
            try:
                idx = headers.index(col_name)
                return str(row[idx].value).strip() if row[idx].value else ""
            except:
                return ""

        for row in sheet.iter_rows(min_row=2):
            if not row[0].value: continue # Pula linhas vazias
            
            # Buscar valor por nome de coluna ou posição
            pat_num = get_val(row, "Patrimonio") or str(row[0].value)
            desc = get_val(row, "Descricao") or str(row[1].value)
            marca = get_val(row, "Marca") or (str(row[2].value) if len(row) > 2 else "")
            modelo = get_val(row, "Modelo") or (str(row[3].value) if len(row) > 3 else "")
            sala_nome = get_val(row, "Sala") or (str(row[4].value) if len(row) > 4 else "Geral")
            foto_url = get_val(row, "Foto") or (str(row[5].value) if len(row) > 5 else "")
            
            # Buscar ou criar sala
            sala = Sala.query.filter_by(nome=sala_nome, escola_id=e_id).first()
            if not sala:
                sala = Sala(nome=sala_nome, bloco='-', escola_id=e_id)
                db.session.add(sala)
                db.session.commit()
            
            # Evitar duplicados por número
            existente = Patrimonio.query.filter_by(numero_patrimonio=pat_num, escola_id=e_id).first()
            if not existente:
                novo_pat = Patrimonio(
                    numero_patrimonio=pat_num,
                    descricao=desc,
                    marca=marca,
                    modelo=modelo,
                    imagem_url=foto_url,
                    sala_id=sala.id,
                    escola_id=e_id
                )
                db.session.add(novo_pat)
                count += 1
        
        db.session.commit()
        flash(f'Sucesso! {count} itens importados via Excel.', 'success')
    except Exception as e:
        flash(f'Erro ao processar Excel: {e}', 'danger')
        
    return redirect(url_for('admin_patrimonios'))

# CRUD Salas
@app.route('/admin/salas', methods=['GET', 'POST'])
@login_required
def admin_salas():
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    e_id = current_user.escola_id
    if request.method == 'POST':
        nova_sala = Sala(
            nome=request.form.get('nome'),
            bloco=request.form.get('bloco'),
            descricao=request.form.get('descricao'),
            escola_id=e_id
        )
        # Vincular Professor(es) se selecionado
        prof_ids = request.form.getlist('professor_ids')
        for pid in prof_ids:
            u = User.query.filter_by(id=pid, escola_id=e_id).first()
            if u: nova_sala.responsaveis.append(u)
            
        db.session.add(nova_sala)
        db.session.commit()
        flash('Ambiente cadastrado e professor vinculado!', 'success')
        
    salas = Sala.query.filter_by(escola_id=e_id).all()
    professores = User.query.filter_by(role='professor', escola_id=e_id).all()
    return render_template('admin/salas.html', salas=salas, professores=professores)

# CRUD Patrimonio
@app.route('/admin/patrimonios', methods=['GET', 'POST'])
@login_required
def admin_patrimonios():
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
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
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    pat = Patrimonio.query.filter_by(id=id, escola_id=current_user.escola_id).first_or_404()
    pat.status = 'descartado'
    pat.status_conservacao = 'descartado'
    db.session.commit()
    flash('Item enviado para descarte!', 'success')
    return redirect(url_for('admin_dashboard'))

# Balanço de Inventário (Resultados Consolidados)
@app.route('/admin/balanco/<int:inv_id>')
@login_required
def admin_balanco_inventario(inv_id):
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    inv = Inventario.query.filter_by(id=inv_id, escola_id=current_user.escola_id).first_or_404()
    
    # Itens esperados vs Registrados
    esperados = Patrimonio.query.filter_by(sala_id=inv.sala_id, status='ativo').all()
    registrados = ItemInventario.query.filter_by(inventario_id=inv.id).all()
    
    confirmados = [r for r in registrados if r.status == 'confirmado']
    faltantes = [p for p in esperados if p.id not in [r.patrimonio_id for r in registrados]]
    fora_de_lugar = [r for r in registrados if r.status == 'fora_de_lugar']
    nao_encontrados = [r for r in registrados if r.status == 'nao_encontrado']
    
    return render_template('admin/balanco.html', 
                           inv=inv, 
                           confirmados=confirmados, 
                           faltantes=faltantes, 
                           fora_de_lugar=fora_de_lugar,
                           nao_encontrados=nao_encontrados)

@app.route('/admin/validar_inventario/<int:inv_id>')
@login_required
def admin_validar_inventario(inv_id):
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    inv = Inventario.query.filter_by(id=inv_id, escola_id=current_user.escola_id).first_or_404()
    inv.status = 'validado'
    db.session.commit()
    flash('Inventário validado e arquivado!', 'success')
    return redirect(url_for('admin_dashboard'))

# CRUD Professores (Com Notificação)
@app.route('/admin/responsaveis', methods=['GET', 'POST'])
@login_required
def admin_responsaveis():
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    e_id = current_user.escola_id
    if request.method == 'POST':
        senha_pura = request.form.get('password')
        novo_u = User(
            username=request.form.get('username'),
            email=request.form.get('email'),
            nome=request.form.get('nome'),
            role=request.form.get('role', 'professor'),
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
        flash('Responsável cadastrado com sucesso!', 'success')
        return redirect(url_for('admin_responsaveis'))
    
    responsaveis = User.query.filter(User.role.in_(['professor', 'coordenador']), User.escola_id == e_id).all()
    salas = Sala.query.filter_by(escola_id=e_id).all()
    return render_template('admin/responsaveis.html', responsaveis=responsaveis, salas=salas)

# Validação de Relocação
@app.route('/admin/relocacao/<int:id>/<string:acao>')
@login_required
def admin_processar_relocacao(id, acao):
    if current_user.role not in ['admin', 'coordenador']: return redirect(url_for('index'))
    req = SolicitacaoRealocacao.query.filter_by(id=id, escola_id=current_user.escola_id).first_or_404()
    if acao == 'aprovar':
        req.status = 'aprovado'
        req.patrimonio.sala_id = req.sala_destino_id
    else:
        req.status = 'recusado'
    db.session.commit()
    return redirect(url_for('admin_dashboard'))

# --- Dashboard Professor ---
@app.route('/professor')
@login_required
def professor_dashboard():
    if current_user.role != 'professor':
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
    return redirect(url_for('professor_dashboard'))

# --- Chat Logic ---
@app.route('/chat/<int:sala_id>', methods=['GET', 'POST'])
@login_required
def chat(sala_id):
    sala = Sala.query.get_or_404(sala_id)
    if request.method == 'POST':
        msg = MensagemChat(
            sala_id=sala_id,
            usuario_id=current_user.id,
            usuario_tipo='adm' if current_user.role in ['admin', 'coordenador'] else 'professor',
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

# --- Inicialização Direcionada (Fresh Start) ---
def seed():
    if not Escola.query.first():
        # Única Estrutura Fixa: SENAI São Paulo
        e1 = Escola(nome='SENAI São Paulo', codigo_senai='SP-01', cidade='São Paulo')
        db.session.add(e1)
        db.session.commit()

        # Admin Master Limpo
        admin = User(username='admin', email='admin@senai.br', nome='Administrador Master', role='admin', escola_id=e1.id)
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
        print("Ambiente Limpo: Sistema pronto para dados reais.")

# Verificação e Reset Forçado para Limpeza
with app.app_context():
    # Para garantir a limpeza total solicitada, vamos resetar nesta execução
    db.drop_all()
    db.create_all()
    seed()

if __name__ == '__main__':
    app.run(debug=True)
