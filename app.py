from flask import Flask, jsonify, request, send_from_directory, session, send_file
from flask_cors import CORS
from database import get_conn, init_db
from auth import verify_user, create_user, init_default_admin, login_required, require_role
from excel_io import export_riai_excel, export_proveedores_excel, import_riai_excel, import_proveedores_excel
from pdf_generator import generate_riai_pdf
import os

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), "static"))
app.secret_key = os.environ.get("SECRET_KEY", "cnh-riai-secret-2026")
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
CORS(app, supports_credentials=True)

with app.app_context():
    init_db()
    init_default_admin()

# ── STATIC ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")

@app.route("/login.html")
def login_page():
    return send_from_directory("static", "login.html")

# ── AUTH ──────────────────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def login():
    d = request.json
    user = verify_user(d.get("username", ""), d.get("password", ""))
    if user:
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["rol"] = user["rol"]
        session.permanent = True
        return jsonify({"status": "ok", "username": user["username"], "rol": user["rol"]})
    return jsonify({"error": "Usuario o contraseña incorrectos"}), 401

@app.route("/api/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return jsonify({"status": "ok"})

@app.route("/api/me")
def me():
    if "user_id" in session:
        return jsonify({"username": session["username"], "rol": session["rol"]})
    return jsonify({"error": "No autenticado"}), 401

# ── USUARIOS ──────────────────────────────────────────────────────────────
@app.route("/api/usuarios", methods=["GET"])
@require_role("admin")
def list_usuarios():
    conn = get_conn()
    rows = conn.execute("SELECT id, username, rol, creado_en FROM usuarios").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/usuarios", methods=["POST"])
@require_role("admin")
def add_usuario():
    d = request.json
    ok = create_user(d.get("username"), d.get("password"), d.get("rol", "operador"))
    if ok:
        return jsonify({"status": "ok"}), 201
    return jsonify({"error": "No se pudo crear (¿usuario duplicado?)"}), 400

@app.route("/api/usuarios/<int:id>", methods=["DELETE"])
@require_role("admin")
def delete_usuario(id):
    conn = get_conn()
    conn.execute("DELETE FROM usuarios WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/usuarios/cambiar-password", methods=["POST"])
@login_required
def cambiar_password():
    d = request.json
    nueva = d.get("password", "")
    if len(nueva) < 6:
        return jsonify({"error": "La contraseña debe tener al menos 6 caracteres"}), 400
    from werkzeug.security import generate_password_hash
    conn = get_conn()
    conn.execute("UPDATE usuarios SET password_hash=? WHERE id=?",
                 (generate_password_hash(nueva), session["user_id"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ── PROVEEDORES ───────────────────────────────────────────────────────────
@app.route("/api/proveedores")
@login_required
def get_proveedores():
    q = request.args.get("q", "").lower()
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM proveedores WHERE LOWER(nombre) LIKE ? OR codigo LIKE ?",
        (f"%{q}%", f"%{q}%")
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ── PIEZAS ────────────────────────────────────────────────────────────────
@app.route("/api/piezas/<numero>")
@login_required
def get_pieza(numero):
    conn = get_conn()
    row = conn.execute("SELECT * FROM piezas WHERE numero_pieza=?", (numero,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else jsonify({}), 200

# ── RIAI ──────────────────────────────────────────────────────────────────
@app.route("/api/riai")
@login_required
def list_riai():
    q = request.args.get("q", "").lower()
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, fecha, numero_pieza, descripcion,
               proveedor_nombre, estado, creado_en
        FROM riai
        WHERE LOWER(numero_pieza) LIKE ?
           OR LOWER(descripcion)  LIKE ?
           OR LOWER(proveedor_nombre) LIKE ?
        ORDER BY id DESC
    """, (f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/riai/<int:id>")
@login_required
def get_riai(id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM riai WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else ("Not found", 404)

@app.route("/api/riai", methods=["POST"])
@require_role("admin", "operador")
def create_riai():
    d = request.json
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO riai (
            fecha, idioma, unidad_long, unidad_peso,
            proveedor_codigo, proveedor_nombre, proveedor_direccion,
            proveedor_contacto, proveedor_email, proveedor_telefono,
            numero_pieza, descripcion, largo, ancho, alto, peso, moq, proyecto,
            emb_identico, colocacion,
            p1_tipo, p1_retornable, p1_material, p1_descripcion,
            p1_largo, p1_ancho, p1_alto, p1_peso_emb, p1_capacidad, p1_peso_bruto,
            p1_cajas_capa, p1_capas,
            p2_tipo, p2_retornable, p2_material, p2_descripcion,
            p2_largo, p2_ancho, p2_alto, p2_peso_emb, p2_capacidad, p2_peso_bruto,
            accesorios, img_caja, img_abierta, img_embalada, img_paletizado,
            ap_elaborado_nombre, ap_elaborado_fecha,
            ap_revisado_nombre, ap_revisado_fecha,
            ap_aprobado_nombre, ap_aprobado_fecha,
            estado
        ) VALUES (
            :fecha, :idioma, :unidad_long, :unidad_peso,
            :proveedor_codigo, :proveedor_nombre, :proveedor_direccion,
            :proveedor_contacto, :proveedor_email, :proveedor_telefono,
            :numero_pieza, :descripcion, :largo, :ancho, :alto, :peso, :moq, :proyecto,
            :emb_identico, :colocacion,
            :p1_tipo, :p1_retornable, :p1_material, :p1_descripcion,
            :p1_largo, :p1_ancho, :p1_alto, :p1_peso_emb, :p1_capacidad, :p1_peso_bruto,
            :p1_cajas_capa, :p1_capas,
            :p2_tipo, :p2_retornable, :p2_material, :p2_descripcion,
            :p2_largo, :p2_ancho, :p2_alto, :p2_peso_emb, :p2_capacidad, :p2_peso_bruto,
            :accesorios, :img_caja, :img_abierta, :img_embalada, :img_paletizado,
            :ap_elaborado_nombre, :ap_elaborado_fecha,
            :ap_revisado_nombre, :ap_revisado_fecha,
            :ap_aprobado_nombre, :ap_aprobado_fecha,
            :estado
        )
    """, d)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id, "status": "ok"}), 201

@app.route("/api/riai/<int:id>", methods=["PUT"])
@require_role("admin", "operador")
def update_riai(id):
    d = request.json
    d["id"] = id
    conn = get_conn()
    conn.execute("""
        UPDATE riai SET
            fecha=:fecha, idioma=:idioma, unidad_long=:unidad_long, unidad_peso=:unidad_peso,
            proveedor_codigo=:proveedor_codigo, proveedor_nombre=:proveedor_nombre,
            proveedor_direccion=:proveedor_direccion, proveedor_contacto=:proveedor_contacto,
            proveedor_email=:proveedor_email, proveedor_telefono=:proveedor_telefono,
            numero_pieza=:numero_pieza, descripcion=:descripcion,
            largo=:largo, ancho=:ancho, alto=:alto, peso=:peso, moq=:moq, proyecto=:proyecto,
            emb_identico=:emb_identico, colocacion=:colocacion,
            p1_tipo=:p1_tipo, p1_retornable=:p1_retornable, p1_material=:p1_material,
            p1_descripcion=:p1_descripcion,
            p1_largo=:p1_largo, p1_ancho=:p1_ancho, p1_alto=:p1_alto,
            p1_peso_emb=:p1_peso_emb, p1_capacidad=:p1_capacidad, p1_peso_bruto=:p1_peso_bruto,
            p1_cajas_capa=:p1_cajas_capa, p1_capas=:p1_capas,
            p2_tipo=:p2_tipo, p2_retornable=:p2_retornable, p2_material=:p2_material,
            p2_descripcion=:p2_descripcion,
            p2_largo=:p2_largo, p2_ancho=:p2_ancho, p2_alto=:p2_alto,
            p2_peso_emb=:p2_peso_emb, p2_capacidad=:p2_capacidad, p2_peso_bruto=:p2_peso_bruto,
            accesorios=:accesorios, img_caja=:img_caja, img_abierta=:img_abierta,
            img_embalada=:img_embalada, img_paletizado=:img_paletizado,
            ap_elaborado_nombre=:ap_elaborado_nombre, ap_elaborado_fecha=:ap_elaborado_fecha,
            ap_revisado_nombre=:ap_revisado_nombre, ap_revisado_fecha=:ap_revisado_fecha,
            ap_aprobado_nombre=:ap_aprobado_nombre, ap_aprobado_fecha=:ap_aprobado_fecha,
            estado=:estado,
            actualizado_en=datetime('now','localtime')
        WHERE id=:id
    """, d)
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/riai/<int:id>", methods=["DELETE"])
@require_role("admin")
def delete_riai(id):
    conn = get_conn()
    conn.execute("DELETE FROM riai WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

# ── ANÁLISIS DE SATURACIÓN (Hugging Face) ────────────────────────────────
@app.route("/api/analizar-saturacion", methods=["POST"])
@login_required
def analizar_saturacion():
    import re, urllib.request, json as json_lib

    d = request.json
    img_b64 = d.get("imagen", "")
    if not img_b64:
        return jsonify({"error": "No se recibió imagen"}), 400

    match = re.search(r'base64,(.*)', img_b64)
    if not match:
        return jsonify({"error": "Formato de imagen inválido"}), 400
    raw_b64 = match.group(1)

    api_key = os.environ.get("HF_API_KEY", "")
    if not api_key:
        return jsonify({"error": "HF_API_KEY no configurada"}), 500

    # Usamos un modelo VLM (vision-language) vía el router de HF, compatible con formato OpenAI
    url = "https://router.huggingface.co/v1/chat/completions"

    payload = {
        "model": "meta-llama/Llama-3.2-11B-Vision-Instruct",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """Analizá esta imagen de una caja de embalaje industrial abierta con piezas adentro.
Estimá el nivel de saturación/llenado de la caja como porcentaje (0 = vacía, 100 = completamente llena).
Respondé ÚNICAMENTE con un número entero entre 0 y 100, sin texto adicional, sin el símbolo %.
Ejemplo de respuesta válida: 75"""
                },
                {
                    "type": "image_url",
                    "image_url": {"url": img_b64}
                }
            ]
        }],
        "max_tokens": 10
    }

    try:
        req = urllib.request.Request(
            url,
            data=json_lib.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=40) as resp:
            result = json_lib.loads(resp.read().decode())
        texto = result["choices"][0]["message"]["content"].strip()
        num = re.search(r'\d+', texto)
        if num:
            pct = min(100, max(0, int(num.group())))
            return jsonify({"saturacion": pct})
        return jsonify({"error": f"No se pudo determinar el nivel. Respuesta: {texto}"}), 400
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"HF HTTPError {e.code}: {error_body}", flush=True)
        return jsonify({"error": f"Error de Hugging Face ({e.code}): {error_body}"}), 500
    except Exception as e:
        print(f"HF Exception: {repr(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

# ── CONTROL ───────────────────────────────────────────────────────────────
@app.route("/api/control")
@login_required
def list_control():
    q = request.args.get("q", "").lower()
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, fecha, numero_pieza, proveedor_nombre,
               largo, ancho, alto, qty_por_caja, creado_en
        FROM control
        WHERE LOWER(numero_pieza) LIKE ?
           OR LOWER(proveedor_nombre) LIKE ?
        ORDER BY id DESC
    """, (f"%{q}%", f"%{q}%")).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

@app.route("/api/control/<int:id>")
@login_required
def get_control(id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM control WHERE id=?", (id,)).fetchone()
    conn.close()
    return jsonify(dict(row)) if row else ("Not found", 404)

@app.route("/api/control", methods=["POST"])
@require_role("admin", "operador")
def create_control():
    d = request.json
    conn = get_conn()
    cur = conn.execute("""
        INSERT INTO control (
            fecha, numero_pieza, proveedor_nombre, proveedor_codigo,
            largo, ancho, alto, qty_por_caja, saturacion,
            img_cerrada, img_abierta, img_etiqueta, notas
        ) VALUES (
            :fecha, :numero_pieza, :proveedor_nombre, :proveedor_codigo,
            :largo, :ancho, :alto, :qty_por_caja, :saturacion,
            :img_cerrada, :img_abierta, :img_etiqueta, :notas
        )
    """, d)
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return jsonify({"id": new_id, "status": "ok"}), 201

@app.route("/api/control/<int:id>", methods=["PUT"])
@require_role("admin", "operador")
def update_control(id):
    d = request.json
    d["id"] = id
    conn = get_conn()
    conn.execute("""
        UPDATE control SET
            fecha=:fecha, numero_pieza=:numero_pieza,
            proveedor_nombre=:proveedor_nombre, proveedor_codigo=:proveedor_codigo,
            largo=:largo, ancho=:ancho, alto=:alto, qty_por_caja=:qty_por_caja,
            saturacion=:saturacion,
            img_cerrada=:img_cerrada, img_abierta=:img_abierta,
            img_etiqueta=:img_etiqueta, notas=:notas
        WHERE id=:id
    """, d)
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/control/<int:id>", methods=["DELETE"])
@require_role("admin")
def delete_control(id):
    conn = get_conn()
    conn.execute("DELETE FROM control WHERE id=?", (id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

@app.route("/api/control/por-pn/<pn>")
@login_required
def control_por_pn(pn):
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, fecha, proveedor_nombre, largo, ancho, alto, qty_por_caja
        FROM control WHERE numero_pieza=? ORDER BY id DESC
    """, (pn,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])

# ── PDF ───────────────────────────────────────────────────────────────────
@app.route("/api/riai/<int:id>/pdf")
@login_required
def riai_pdf(id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM riai WHERE id=?", (id,)).fetchone()
    conn.close()
    if not row:
        return jsonify({"error": "RIAI no encontrado"}), 404
    d = dict(row)
    lang = request.args.get("lang", d.get("idioma") or "es")
    buf = generate_riai_pdf(d, lang=lang)
    filename = f"RIAI_{d.get('numero_pieza','sin_pn')}.pdf"
    return send_file(buf, as_attachment=True, download_name=filename,
                     mimetype="application/pdf")

# ── EXCEL ─────────────────────────────────────────────────────────────────
@app.route("/api/export/riai")
@login_required
def export_riai():
    buf = export_riai_excel()
    return send_file(buf, as_attachment=True, download_name="RIAIs_export.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/api/export/proveedores")
@login_required
def export_proveedores():
    buf = export_proveedores_excel()
    return send_file(buf, as_attachment=True, download_name="Proveedores_export.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/api/import/riai", methods=["POST"])
@require_role("admin", "operador")
def import_riai():
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    file = request.files["file"]
    inserted, errors = import_riai_excel(file.stream)
    return jsonify({"status": "ok", "inserted": inserted, "errors": errors})

@app.route("/api/import/proveedores", methods=["POST"])
@require_role("admin", "operador")
def import_proveedores():
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    file = request.files["file"]
    inserted, errors = import_proveedores_excel(file.stream)
    return jsonify({"status": "ok", "inserted": inserted, "errors": errors})

# ── RUN ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("✅ Base de datos lista")
    print("🚀 Servidor corriendo en http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
