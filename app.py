from flask import Flask, jsonify, request, send_from_directory, session, send_file
from flask_cors import CORS
from database import get_conn, init_db
from auth import verify_user, create_user, init_default_admin, login_required, require_role
from excel_io import (
    export_riai_excel, export_proveedores_excel, import_riai_excel, import_proveedores_excel,
    export_control_excel, import_pn_proveedores_excel, export_pn_proveedores_excel,
)
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
    resultado = dict(row) if row else {}

    proveedores = conn.execute(
        "SELECT proveedor_codigo, proveedor_nombre FROM pn_proveedores WHERE numero_pieza=? ORDER BY proveedor_nombre",
        (numero,)
    ).fetchall()
    resultado["proveedores"] = [dict(p) for p in proveedores]

    ultimo = conn.execute(
        "SELECT fecha, proveedor_nombre, qty_por_caja, saturacion FROM control WHERE numero_pieza=? ORDER BY fecha DESC, id DESC LIMIT 1",
        (numero,)
    ).fetchone()
    resultado["ultimo_control"] = dict(ultimo) if ultimo else None

    conn.close()
    return jsonify(resultado), 200

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


# Campos nuevos de la Packaging Card. Se completan con None si el frontend
# todavía no los manda (por ejemplo, mientras se termina de conectar el
# formulario nuevo), para que el INSERT/UPDATE no rompa por faltar una key.
CAMPOS_PACKAGING_CARD_NUEVOS = [
    "p1_ispm", "p1_property", "p1_code", "p1_other",
    "p2_ispm", "p2_property", "p2_code", "p2_other",
    "p2_collapsible", "p2_collapsed_height", "p2_collapsed_layers",
    "ps_tipo", "ps_retornable", "ps_material", "ps_ispm", "ps_property",
    "ps_code", "ps_other", "ps_descripcion",
    "ps_largo", "ps_ancho", "ps_alto", "ps_peso_emb", "ps_capacidad", "ps_peso_bruto",
    "ps_collapsible", "ps_collapsed_height", "ps_collapsed_layers",
    "su_static", "su_dynamic",
]

def _completar_defaults_riai(d):
    for campo in CAMPOS_PACKAGING_CARD_NUEVOS:
        d.setdefault(campo, None)
    return d


@app.route("/api/riai", methods=["POST"])
@require_role("admin", "operador")
def create_riai():
    d = _completar_defaults_riai(request.json)
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
            p1_cajas_capa, p1_capas, p1_ispm, p1_property, p1_code, p1_other,
            p2_tipo, p2_retornable, p2_material, p2_descripcion,
            p2_largo, p2_ancho, p2_alto, p2_peso_emb, p2_capacidad, p2_peso_bruto,
            p2_ispm, p2_property, p2_code, p2_other,
            p2_collapsible, p2_collapsed_height, p2_collapsed_layers,
            ps_tipo, ps_retornable, ps_material, ps_descripcion,
            ps_largo, ps_ancho, ps_alto, ps_peso_emb, ps_capacidad, ps_peso_bruto,
            ps_ispm, ps_property, ps_code, ps_other,
            ps_collapsible, ps_collapsed_height, ps_collapsed_layers,
            su_static, su_dynamic,
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
            :p1_cajas_capa, :p1_capas, :p1_ispm, :p1_property, :p1_code, :p1_other,
            :p2_tipo, :p2_retornable, :p2_material, :p2_descripcion,
            :p2_largo, :p2_ancho, :p2_alto, :p2_peso_emb, :p2_capacidad, :p2_peso_bruto,
            :p2_ispm, :p2_property, :p2_code, :p2_other,
            :p2_collapsible, :p2_collapsed_height, :p2_collapsed_layers,
            :ps_tipo, :ps_retornable, :ps_material, :ps_descripcion,
            :ps_largo, :ps_ancho, :ps_alto, :ps_peso_emb, :ps_capacidad, :ps_peso_bruto,
            :ps_ispm, :ps_property, :ps_code, :ps_other,
            :ps_collapsible, :ps_collapsed_height, :ps_collapsed_layers,
            :su_static, :su_dynamic,
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
    d = _completar_defaults_riai(request.json)
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
            p1_ispm=:p1_ispm, p1_property=:p1_property, p1_code=:p1_code, p1_other=:p1_other,
            p2_tipo=:p2_tipo, p2_retornable=:p2_retornable, p2_material=:p2_material,
            p2_descripcion=:p2_descripcion,
            p2_largo=:p2_largo, p2_ancho=:p2_ancho, p2_alto=:p2_alto,
            p2_peso_emb=:p2_peso_emb, p2_capacidad=:p2_capacidad, p2_peso_bruto=:p2_peso_bruto,
            p2_ispm=:p2_ispm, p2_property=:p2_property, p2_code=:p2_code, p2_other=:p2_other,
            p2_collapsible=:p2_collapsible, p2_collapsed_height=:p2_collapsed_height,
            p2_collapsed_layers=:p2_collapsed_layers,
            ps_tipo=:ps_tipo, ps_retornable=:ps_retornable, ps_material=:ps_material,
            ps_descripcion=:ps_descripcion,
            ps_largo=:ps_largo, ps_ancho=:ps_ancho, ps_alto=:ps_alto,
            ps_peso_emb=:ps_peso_emb, ps_capacidad=:ps_capacidad, ps_peso_bruto=:ps_peso_bruto,
            ps_ispm=:ps_ispm, ps_property=:ps_property, ps_code=:ps_code, ps_other=:ps_other,
            ps_collapsible=:ps_collapsible, ps_collapsed_height=:ps_collapsed_height,
            ps_collapsed_layers=:ps_collapsed_layers,
            su_static=:su_static, su_dynamic=:su_dynamic,
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

# ── ANÁLISIS DE SATURACIÓN (modelo propio, vía app_saturacion en Railway) ──
@app.route("/api/analizar-saturacion", methods=["POST"])
@login_required
def analizar_saturacion():
    import re, base64, requests

    d = request.json
    img_b64 = d.get("imagen", "")
    if not img_b64:
        return jsonify({"error": "No se recibió imagen"}), 400

    match = re.search(r'base64,(.*)', img_b64)
    if not match:
        return jsonify({"error": "Formato de imagen inválido"}), 400
    raw_b64 = match.group(1)

    saturacion_api_url = os.environ.get("SATURACION_API_URL", "")
    if saturacion_api_url and not saturacion_api_url.startswith(("http://", "https://")):
        saturacion_api_url = f"https://{saturacion_api_url}"
    saturacion_api_key = os.environ.get("SATURACION_API_KEY", "")
    if not saturacion_api_url:
        return jsonify({"error": "SATURACION_API_URL no configurada"}), 500

    try:
        imagen_bytes = base64.b64decode(raw_b64)
    except Exception:
        return jsonify({"error": "No se pudo decodificar la imagen"}), 400

    def _llamar_api_saturacion():
        return requests.post(
            f"{saturacion_api_url.rstrip('/')}/api/saturacion",
            files={"foto": ("foto.jpg", imagen_bytes, "image/jpeg")},
            headers={"X-API-Key": saturacion_api_key} if saturacion_api_key else {},
            timeout=40,
        )

    import time
    data = None
    ultimo_error = None
    # hasta 2 intentos: el servicio de saturación puede tardar en "despertar"
    # (cold start) si estuvo un rato sin uso, y la primera petición se pierde
    for intento in range(2):
        resp = None
        try:
            resp = _llamar_api_saturacion()
        except requests.exceptions.RequestException as e:
            ultimo_error = f"No se pudo conectar con el servicio de análisis: {e}"
            print(f"Error de conexión a app_saturacion (intento {intento + 1}): {repr(e)}", flush=True)

        if resp is not None:
            try:
                data = resp.json()
                break
            except ValueError:
                # incluye requests.exceptions.JSONDecodeError, que hereda de
                # RequestException Y de ValueError -- por eso este bloque va
                # SEPARADO del try de arriba, si no el except de conexión se
                # lo come primero y perdemos el detalle real del problema
                ultimo_error = (
                    f"El servicio de análisis respondió algo inesperado (status {resp.status_code}). "
                    f"Puede estar caído o reiniciándose."
                )
                print(f"Respuesta no-JSON de app_saturacion (intento {intento + 1}). "
                      f"Status: {resp.status_code}. Body: {resp.text[:300]!r}", flush=True)

        if intento == 0:
            time.sleep(3)  # le da tiempo al contenedor a terminar de levantar

    if data is None:
        return jsonify({"error": ultimo_error}), 502

    if not data.get("ok"):
        return jsonify({"error": data.get("detalle", "El modelo no pudo analizar la imagen")}), 400

    pct = round(data["saturacion"])
    return jsonify({"saturacion": pct})

# ── CONTROL ───────────────────────────────────────────────────────────────
@app.route("/api/control")
@login_required
def list_control():
    q = request.args.get("q", "").lower()
    conn = get_conn()
    rows = conn.execute("""
        SELECT id, fecha, numero_pieza, proveedor_nombre,
               largo, ancho, alto, qty_por_caja, saturacion,
               (img_abierta IS NOT NULL AND img_abierta != '') AS tiene_img_abierta,
               creado_en
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

@app.route("/api/export/control")
@login_required
def export_control():
    buf = export_control_excel()
    return send_file(buf, as_attachment=True, download_name="Control_export.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

@app.route("/api/export/pn_proveedores")
@login_required
def export_pn_proveedores():
    buf = export_pn_proveedores_excel()
    return send_file(buf, as_attachment=True, download_name="PN_Proveedores_export.xlsx",
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

@app.route("/api/import/pn_proveedores", methods=["POST"])
@require_role("admin", "operador")
def import_pn_proveedores():
    if "file" not in request.files:
        return jsonify({"error": "No se envió ningún archivo"}), 400
    file = request.files["file"]
    inserted, errors = import_pn_proveedores_excel(file.stream)
    return jsonify({"status": "ok", "inserted": inserted, "errors": errors})

# ── RUN ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("✅ Base de datos lista")
    print("🚀 Servidor corriendo en http://localhost:5000")
    app.run(debug=True, host="0.0.0.0", port=5000)
