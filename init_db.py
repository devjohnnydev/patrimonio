from app import app, db, seed

with app.app_context():
    db.create_all()
    seed()
    print("Banco de dados inicializado e Admin criado.")
