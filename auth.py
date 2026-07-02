from werkzeug.security import generate_password_hash, check_password_hash
from database import get_conn
from functools import wraps
from flask import session, jsonify


def verify_user(username, password):
    conn = get_conn()
    row = conn.execute("SELECT * FROM usuarios WHERE username=?", (username,)).fetchone()
    conn.close()
    if row and check_password_hash(row["password_hash"], password):
        return {"id": row["id"], "username": row["username"], "rol": row["rol"]}
    return None


def create_user(username, password, rol="operador"):
    conn = get_conn()
    pw_hash = generate_password_hash(password)
    try:
        conn.execute(
            "INSERT INTO usuarios (username, password_hash, rol) VALUES (?,?,?)",
            (username, pw_hash, rol)
        )
        conn.commit()
        return True
    except Exception as e:
        print("Error creando usuario:", e)
        return False
    finally:
        conn.close()


def init_default_admin():
    conn = get_conn()
    count = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
    conn.close()
    if count == 0:
        create_user("admin", "admin123", "admin")
        print("✅ Usuario admin creado -> usuario: admin / contraseña: admin123 (CAMBIALA)")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "No autenticado"}), 401
        return fn(*args, **kwargs)
    return wrapper


def require_role(*roles):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if "user_id" not in session:
                return jsonify({"error": "No autenticado"}), 401
            if session.get("rol") not in roles:
                return jsonify({"error": "Sin permisos"}), 403
            return fn(*args, **kwargs)
        return wrapper
    return decorator
