from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from io import BytesIO
import base64, re

ROJO        = colors.HexColor("#C8102E")
GRIS_CLARO  = colors.HexColor("#E8E8E8")
GRIS_OSCURO = colors.HexColor("#555555")
BLANCO      = colors.white
NEGRO       = colors.HexColor("#222222")

LABELS = {
    "es": {
        "title":"CARTÃO DE EMBALAGEM","lang":"IDIOMA","unitlen":"UNIDAD LONGITUD","unitwt":"UNIDAD PESO","date":"FECHA",
        "supplier":"INFORMACIONES DEL PROVEEDOR","cscn":"CÓDIGO CSCN","suppname":"NOMBRE DEL PROVEEDOR",
        "suppaddr":"DIRECCIÓN DE ENVÍO","suppcontact":"PERSONA DE CONTACTO","suppemail":"E-MAIL","suppphone":"TELÉFONO",
        "piece":"DATOS DETALLADOS DE LA PIEZA","pn":"N° DE PIEZA (PN)","pndesc":"DESCRIPCIÓN",
        "dim":"DIMENSIÓN [mm]","peso":"PESO PIEZA [KG]","moq":"MOQ","proyecto":"PROYECTO",
        "pkgmain":"INFORMACIONES PRINCIPALES DE EMBALAJE","same":"¿Embalaje primario y secundario idénticos?",
        "emb_prim":"EMBALAJE PRIMARIO","emb_sec":"EMBALAJE SECUNDARIO","emb_unico":"EMBALAJE",
        "tipo":"TIPO","ret":"RETORNABLE","desc":"DESCRIPCIÓN","largo":"LARGO","ancho":"ANCHO","alto":"ALTO",
        "pesovacio":"PESO VACÍO [KG]","cap":"CAPACIDAD [pcs]","pesobruto":"PESO BRUTO [KG]",
        "accesorios":"ACCESORIOS DE EMBALAJE",
        "imgs":"IMÁGENES","img1":"Visión interna","img2":"Visión externa abierta","img3":"Visión externa cerrada",
        "img4":"Análisis de paletizado",
        "aprobacion":"APROBACIÓN","depto":"DEPARTAMENTO","nombre":"NOMBRE","fecha_col":"FECHA","notas_col":"NOTAS",
        "englog":"Ingeniería Logística (CNH)","prov":"Proveedor",
        "aviso":"EL EMBALAJE DEBE ESTAR EN CONFORMIDAD CON LAS ORIENTACIONES DEL MANUAL DE EMBALAJE CNH GLOBAL DISPONIBLE EN EL PORTAL DEL PROVEEDOR",
        "si":"SÍ","no":"NO",
    },
    "pt": {
        "title":"CARTÃO DE EMBALAGEM","lang":"LINGUAGEM","unitlen":"COMPRIMENTO UM","unitwt":"PESO UM","date":"DATA",
        "supplier":"INFORMAÇÕES DO FORNECEDOR","cscn":"CÓDIGO CSCN","suppname":"NOME DO FORNECEDOR",
        "suppaddr":"ENDEREÇO DE ENVIO","suppcontact":"PESSOA DE CONTATO","suppemail":"E-MAIL","suppphone":"TELEFONE",
        "piece":"DADOS DETALHADOS DA PEÇA","pn":"N° DA PEÇA (PN)","pndesc":"DESCRIÇÃO",
        "dim":"DIMENÇÃO [mm]","peso":"PESO DA PEÇA [KG]","moq":"MOQ","projeto":"PROJETO",
        "pkgmain":"INFORMAÇÕES PRINCIPAIS DA EMBALAGEM","same":"A embalagem primária e secundária são idênticas?",
        "emb_prim":"EMBALAGEM PRIMÁRIA","emb_sec":"EMBALAGEM SECUNDÁRIA","emb_unico":"EMBALAGEM",
        "tipo":"TIPO","ret":"RETORNÁVEL","desc":"DESCRIÇÃO","largo":"COMPRIMENTO","ancho":"LARGURA","alto":"ALTURA",
        "pesovacio":"PESO VAZIO [KG]","cap":"CAPACIDADE [pcs]","pesobruto":"PESO BRUTO [KG]",
        "accesorios":"ACESSÓRIOS DE EMBALAGEM",
        "imgs":"IMAGENS","img1":"Visão interna","img2":"Visão externa aberta","img3":"Visão externa fechada",
        "img4":"Análise de paletização",
        "aprobacion":"APROVAÇÃO","depto":"DEPARTAMENTO","nombre":"NOME","fecha_col":"DATA","notas_col":"NOTAS",
        "englog":"Engenharia Logística (CNH)","prov":"Fornecedor",
        "aviso":"A EMBALAGEM DEVE ESTAR EM CONFORMIDADE COM AS ORIENTAÇÕES DO MANUAL DE EMBALAGEM DA CNH GLOBAL DISPONÍVEL NO PORTAL DO FORNECEDOR",
        "si":"SIM","no":"NÃO",
    },
    "en": {
        "title":"PACKAGING CARD","lang":"LANGUAGE","unitlen":"LENGTH UNIT","unitwt":"WEIGHT UNIT","date":"DATE",
        "supplier":"SUPPLIER INFORMATION","cscn":"CSCN CODE","suppname":"SUPPLIER NAME",
        "suppaddr":"SHIPPING ADDRESS","suppcontact":"CONTACT PERSON","suppemail":"E-MAIL","suppphone":"PHONE",
        "piece":"DETAILED PART DATA","pn":"PART NUMBER (PN)","pndesc":"DESCRIPTION",
        "dim":"DIMENSION [mm]","peso":"PART WEIGHT [KG]","moq":"MOQ","proyecto":"PROJECT",
        "pkgmain":"MAIN PACKAGING INFORMATION","same":"Are primary and secondary packaging identical?",
        "emb_prim":"PRIMARY PACKAGING","emb_sec":"SECONDARY PACKAGING","emb_unico":"PACKAGING",
        "tipo":"TYPE","ret":"RETURNABLE","desc":"DESCRIPTION","largo":"LENGTH","ancho":"WIDTH","alto":"HEIGHT",
        "pesovacio":"EMPTY WEIGHT [KG]","cap":"CAPACITY [pcs]","pesobruto":"GROSS WEIGHT [KG]",
        "accesorios":"PACKAGING ACCESSORIES",
        "imgs":"IMAGES","img1":"Internal view","img2":"External view open","img3":"External view closed",
        "img4":"Palletizing analysis",
        "aprobacion":"APPROVAL","depto":"DEPARTMENT","nombre":"NAME","fecha_col":"DATE","notas_col":"NOTES",
        "englog":"Logistics Engineering (CNH)","prov":"Supplier",
        "aviso":"PACKAGING MUST COMPLY WITH CNH GLOBAL PACKAGING MANUAL GUIDELINES AVAILABLE ON THE SUPPLIER PORTAL",
        "si":"YES","no":"NO",
    },
}

PAGE_W, PAGE_H = A4
MARGIN = 10 * mm
CONTENT_W = PAGE_W - 2 * MARGIN


def _b64_to_image(b64_str, max_w=55*mm, max_h=40*mm):
    if not b64_str or len(b64_str) < 20:
        return None
    try:
        match = re.search(r'base64,(.*)', b64_str)
        raw = match.group(1) if match else b64_str
        img_data = base64.b64decode(raw)
        buf = BytesIO(img_data)
        img = RLImage(buf, width=max_w, height=max_h)
        img.hAlign = 'CENTER'
        return img
    except Exception:
        return None


def _st(size=7, bold=False, color=NEGRO, align=TA_LEFT):
    return ParagraphStyle('c', fontName='Helvetica-Bold' if bold else 'Helvetica',
                          fontSize=size, leading=size+2, textColor=color, alignment=align)


def _lv(label, value, ls=5.5, vs=8):
    txt = (f'<font size="{ls}" color="#888888">{label}</font>'
           f'<br/><font size="{vs}"><b>{value or "—"}</b></font>')
    return Paragraph(txt, _st())


def _red_bar(text):
    t = Table([[Paragraph(f'<font color="white" size="8"><b>{text}</b></font>',
                           _st(align=TA_CENTER))]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),ROJO),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    return t


def _gray_bar(text):
    t = Table([[Paragraph(f'<font size="7"><b>{text}</b></font>',
                           _st(align=TA_CENTER))]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),GRIS_CLARO),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
    ]))
    return t


def _grid(rows, col_widths, bg=None):
    t = Table(rows, colWidths=col_widths)
    style = [
        ('BOX',(0,0),(-1,-1),0.5,colors.grey),
        ('INNERGRID',(0,0),(-1,-1),0.5,colors.grey),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
        ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
        ('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
    ]
    if bg:
        style.append(('BACKGROUND',(0,0),(-1,-1),bg))
    t.setStyle(TableStyle(style))
    return t


def _pkg_block(d, prefix, title, L):
    g = lambda k: str(d.get(k) or "—")
    rows = [
        [_lv(L["tipo"], g(f"{prefix}_tipo")),
         _lv(L["ret"], g(f"{prefix}_retornable")),
         _lv(L["desc"], g(f"{prefix}_descripcion")),
         _lv(L["largo"], g(f"{prefix}_largo")),
         _lv(L["ancho"], g(f"{prefix}_ancho")),
         _lv(L["alto"], g(f"{prefix}_alto"))],
        [_lv(L["pesovacio"], g(f"{prefix}_peso_emb")),
         _lv(L["cap"], g(f"{prefix}_capacidad")),
         _lv(L["pesobruto"], g(f"{prefix}_peso_bruto")),
         Paragraph("", _st()), Paragraph("", _st()), Paragraph("", _st())],
    ]
    return [_gray_bar(title), _grid(rows, [CONTENT_W/6]*6)]


def generate_riai_pdf(d, lang="es"):
    L = LABELS.get(lang, LABELS["es"])
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                             leftMargin=MARGIN, rightMargin=MARGIN,
                             topMargin=MARGIN, bottomMargin=MARGIN)
    story = []
    g = lambda k: str(d.get(k) or "—")

    # ── HEADER ────────────────────────────────────────────────────────────
    header = Table([[
        Paragraph("", _st()),
        Paragraph(L["title"], _st(size=16, bold=True, align=TA_CENTER)),
        Paragraph('<font color="#C8102E" size="18"><b>CNH</b></font><br/>'
                  '<font size="6" color="#555">Industrial</font>', _st(align=TA_CENTER))
    ]], colWidths=[CONTENT_W*0.15, CONTENT_W*0.65, CONTENT_W*0.20])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'MIDDLE')]))
    story.append(header)
    story.append(Spacer(1,3))

    # idioma / unidades / fecha
    lang_map = {"es":"Español","pt":"Português","en":"English"}
    story.append(_grid([[
        _lv(L["lang"], lang_map.get(lang, lang)),
        _lv(L["unitlen"], g("unidad_long")),
        _lv(L["unitwt"], g("unidad_peso")),
        _lv(L["date"], g("fecha")),
    ]], [CONTENT_W*0.25]*4))
    story.append(Spacer(1,3))

    # ── PROVEEDOR ─────────────────────────────────────────────────────────
    story.append(_red_bar(L["supplier"]))
    story.append(_grid([[
        _lv(L["cscn"], g("proveedor_codigo")),
        _lv(L["suppname"], g("proveedor_nombre")),
        _lv(L["suppaddr"], g("proveedor_direccion")),
    ]], [CONTENT_W*0.2, CONTENT_W*0.35, CONTENT_W*0.45]))
    story.append(_grid([[
        _lv(L["suppcontact"], g("proveedor_contacto")),
        _lv(L["suppemail"], g("proveedor_email")),
        _lv(L["suppphone"], g("proveedor_telefono")),
    ]], [CONTENT_W/3]*3))
    story.append(Spacer(1,3))

    # ── PIEZA ─────────────────────────────────────────────────────────────
    story.append(_red_bar(L["piece"]))
    dim = f'{g("largo")} × {g("ancho")} × {g("alto")}'
    story.append(_grid([[
        _lv(L["pn"], g("numero_pieza"), vs=11),
        _lv(L["pndesc"], g("descripcion")),
        _lv(L["dim"], dim),
        _lv(L["peso"], g("peso")),
        _lv(L["moq"], g("moq")),
        _lv(L.get("proyecto","Proyecto"), g("proyecto")),
    ]], [CONTENT_W*0.18, CONTENT_W*0.27, CONTENT_W*0.22, CONTENT_W*0.13, CONTENT_W*0.10, CONTENT_W*0.10]))
    story.append(Spacer(1,3))

    # ── EMBALAJE ──────────────────────────────────────────────────────────
    story.append(_red_bar(L["pkgmain"]))
    same = d.get("emb_identico") == 1
    story.append(_grid([[_lv(L["same"], L["si"] if same else L["no"], vs=9)]], [CONTENT_W]))

    if same:
        for el in _pkg_block(d, "p1", L["emb_unico"], L): story.append(el)
    else:
        for el in _pkg_block(d, "p1", L["emb_prim"], L): story.append(el)
        story.append(Spacer(1,2))
        for el in _pkg_block(d, "p2", L["emb_sec"], L): story.append(el)
    story.append(Spacer(1,3))

    # ── ACCESORIOS ────────────────────────────────────────────────────────
    story.append(_red_bar(L["accesorios"]))
    story.append(_grid([[Paragraph(
        f'<font size="7">{g("accesorios")}</font>', _st())
    ]], [CONTENT_W], ))
    story.append(Spacer(1,3))

    # ── IMÁGENES ──────────────────────────────────────────────────────────
    story.append(_red_bar(L["imgs"]))
    img1 = _b64_to_image(d.get("img_caja"))
    img2 = _b64_to_image(d.get("img_abierta"))
    img3 = _b64_to_image(d.get("img_embalada"))
    img_row = [
        img1 or Paragraph(L["img1"], _st(align=TA_CENTER)),
        img2 or Paragraph(L["img2"], _st(align=TA_CENTER)),
        img3 or Paragraph(L["img3"], _st(align=TA_CENTER)),
    ]
    img_tbl = Table([img_row], colWidths=[CONTENT_W/3]*3, rowHeights=[40*mm])
    img_tbl.setStyle(TableStyle([
        ('BOX',(0,0),(-1,-1),0.5,colors.grey),
        ('INNERGRID',(0,0),(-1,-1),0.5,colors.grey),
        ('ALIGN',(0,0),(-1,-1),'CENTER'),
        ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
    ]))
    story.append(img_tbl)
    story.append(Spacer(1,3))

    # ── AVISO ─────────────────────────────────────────────────────────────
    aviso = Table([[Paragraph(L["aviso"], _st(size=6, bold=True, align=TA_CENTER))]], colWidths=[CONTENT_W])
    aviso.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1),GRIS_CLARO),
        ('BOX',(0,0),(-1,-1),0.5,colors.grey),
        ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
    ]))
    story.append(aviso)
    story.append(Spacer(1,3))

    # ── APROBACIÓN ────────────────────────────────────────────────────────
    story.append(_red_bar(L["aprobacion"]))
    story.append(_grid([[
        Paragraph(f'<font size="6.5"><b>{L["depto"]}</b></font>', _st()),
        Paragraph(f'<font size="6.5"><b>{L["nombre"]}</b></font>', _st()),
        Paragraph(f'<font size="6.5"><b>{L["fecha_col"]}</b></font>', _st()),
        Paragraph(f'<font size="6.5"><b>{L["notas_col"]}</b></font>', _st()),
    ]], [CONTENT_W*0.30, CONTENT_W*0.30, CONTENT_W*0.20, CONTENT_W*0.20], bg=GRIS_CLARO))
    story.append(_grid([
        [Paragraph(L["englog"], _st(size=7)),
         Paragraph(g("ap_aprobado_nombre"), _st(size=7)),
         Paragraph(g("ap_aprobado_fecha"), _st(size=7)),
         Paragraph("", _st())],
        [Paragraph(L["prov"], _st(size=7)),
         Paragraph(g("ap_elaborado_nombre"), _st(size=7)),
         Paragraph(g("ap_elaborado_fecha"), _st(size=7)),
         Paragraph("", _st())],
    ], [CONTENT_W*0.30, CONTENT_W*0.30, CONTENT_W*0.20, CONTENT_W*0.20],
    ))

    # ── ANEXO — PALETIZADO (página 2 si hay imagen) ───────────────────────
    img_pal = _b64_to_image(d.get("img_paletizado"), max_w=160*mm, max_h=180*mm)
    if img_pal:
        from reportlab.platypus import PageBreak
        story.append(PageBreak())
        story.append(_red_bar(L.get("img4", "ANÁLISIS DE PALETIZADO")))
        story.append(Spacer(1, 5))
        pal_tbl = Table([[img_pal]], colWidths=[CONTENT_W], rowHeights=[180*mm])
        pal_tbl.setStyle(TableStyle([
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('BOX',(0,0),(-1,-1),0.5,colors.grey),
        ]))
        story.append(pal_tbl)

    doc.build(story)
    buf.seek(0)
    return buf
