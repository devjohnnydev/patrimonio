from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()

# --- Entidade SaaS Principal ---
class Escola(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    codigo_senai = db.Column(db.String(20), unique=True)
    cidade = db.Column(db.String(100))
    
    usuarios = db.relationship('User', backref='escola', lazy=True)
    salas = db.relationship('Sala', backref='escola', lazy=True)
    patrimonios = db.relationship('Patrimonio', backref='escola', lazy=True)

# Tabela de associação para Responsáveis e Salas
responsavel_salas = db.Table('responsavel_salas',
    db.Column('user_id', db.Integer, db.ForeignKey('user.id'), primary_key=True),
    db.Column('sala_id', db.Integer, db.ForeignKey('sala.id'), primary_key=True)
)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='professor')  # 'admin', 'coordenador', 'professor'
    nome = db.Column(db.String(100), nullable=False)
    foto_url = db.Column(db.String(500)) # Foto de perfil
    
    salas = db.relationship('Sala', secondary=responsavel_salas, backref=db.backref('responsaveis', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Sala(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    nome = db.Column(db.String(100), nullable=False)
    bloco = db.Column(db.String(50))
    descricao = db.Column(db.Text)
    imagem_url = db.Column(db.String(500))
    
    patrimonios = db.relationship('Patrimonio', backref='sala', lazy=True)

class Patrimonio(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    numero_patrimonio = db.Column(db.String(50), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=False)
    marca = db.Column(db.String(100))
    modelo = db.Column(db.String(100))
    status = db.Column(db.String(20), default='ativo') # 'ativo', 'inativo', 'descartado'
    status_conservacao = db.Column(db.String(20), default='bom') # 'bom', 'quebrado'
    imagem_url = db.Column(db.String(500))
    sala_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)

class Inventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    sala_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    data_hora_inicio = db.Column(db.DateTime, default=datetime.utcnow)
    data_hora_fim = db.Column(db.DateTime)
    data_limite = db.Column(db.DateTime) # Prazo final planejado
    status = db.Column(db.String(20), default='iniciado')
    assinatura_base64 = db.Column(db.Text) # Desenho da assinatura manuscrita

    sala = db.relationship('Sala', backref='inventarios')
    responsavel = db.relationship('User', backref='inventarios')
    escola = db.relationship('Escola', backref='inventarios')

class ItemInventario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    inventario_id = db.Column(db.Integer, db.ForeignKey('inventario.id'), nullable=False)
    patrimonio_id = db.Column(db.Integer, db.ForeignKey('patrimonio.id'), nullable=True)
    sala_id_da_vez = db.Column(db.Integer, db.ForeignKey('sala.id'))
    status = db.Column(db.String(30)) # 'confirmado', 'alterado', 'fora_de_lugar', 'nao_encontrado'
    status_conservacao_visto = db.Column(db.String(20))
    foto_validacao_url = db.Column(db.String(500)) # Foto tirada no balanço
    observacao = db.Column(db.Text)

class SolicitacaoRealocacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    patrimonio_id = db.Column(db.Integer, db.ForeignKey('patrimonio.id'), nullable=False)
    sala_origem_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)
    sala_destino_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)
    responsavel_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pendente')
    observacao = db.Column(db.Text)
    data_solicitacao = db.Column(db.DateTime, default=datetime.utcnow)

    patrimonio = db.relationship('Patrimonio', backref='solicitacoes')
    sala_origem = db.relationship('Sala', foreign_keys=[sala_origem_id])
    sala_destino = db.relationship('Sala', foreign_keys=[sala_destino_id])
    responsavel = db.relationship('User', backref='solicitacoes')

class MensagemChat(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    escola_id = db.Column(db.Integer, db.ForeignKey('escola.id'), nullable=False)
    sala_id = db.Column(db.Integer, db.ForeignKey('sala.id'), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    usuario_tipo = db.Column(db.String(20))
    texto = db.Column(db.Text, nullable=False)
    data_hora = db.Column(db.DateTime, default=datetime.utcnow)
    lida = db.Column(db.Boolean, default=False)

    usuario = db.relationship('User', backref='mensagens')
    sala = db.relationship('Sala', backref='mensagens')
