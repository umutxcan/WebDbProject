#eskisi not.txtde
from flask import Flask, jsonify
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://myuser:mypassword@myapp-db/mydatabase'
db = SQLAlchemy(app)

class User(db.Model):
    __tablename__ = 'users4'  #sonradan eklendi calıstı dokunma sakın
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50))
    email = db.Column(db.String(100))

@app.route('/users')
def get_users():
    users = User.query.all()
    return jsonify([{'username': u.username, 'email': u.email} for u in users])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)