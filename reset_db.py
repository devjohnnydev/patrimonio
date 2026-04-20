from app import app, db

with app.app_context():
    print("Iniciando limpeza total do banco de dados...")
    db.drop_all()
    print("Tabelas removidas. Criando novas tabelas com a estrutura SaaS...")
    db.create_all()
    print("Sucesso! O banco de dados foi resetado e a estrutura está atualizada.")
    
    # Rodar o seed para garantir que o Admin exista
    from app import seed
    seed()
    print("Seed finalizado.")
