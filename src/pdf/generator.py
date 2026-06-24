from io import BytesIO
from PIL import Image

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from config.constants import LOGO_PATH


# =========================
# GENERACIÓN DEL PDF CON REPORTLAB
# =========================

def generate_pdf(map_image: Image.Image) -> bytes:

    # ==========================================================
    # Estilos para el PDF
    # ==========================================================

    # ── Estilos de texto ───────────────────────────────────────────
    title_style = ParagraphStyle(
        name="TituloPrincipal",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
        leading=20,
    )

    map_title_style = ParagraphStyle(
        name="TituloMapa",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_LEFT,
        spaceAfter=4,
        spaceBefore=0,
        leading=16,
    )

    # ── Estilos de texto de la leyenda ─────────────────────────────
    legend_title_style = ParagraphStyle(
        name="TituloLeyenda",
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=15,
    )

    legend_label_style = ParagraphStyle(
        name="EtiquetaLeyenda",
        fontName="Helvetica",
        fontSize=12,
        textColor=colors.HexColor('#1A1A1A'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=14,
    )

    # ==========================================================
    # Dimensiones del documento
    # ==========================================================

    buffer = BytesIO()

    page_w, page_h = letter     # ancho y altura total del documento
    side_margin = 2.5 * cm      # margen de los lados
    header_h    = 2 * cm        # altura total de la zona del header
    footer_h    = 2 * cm        # altura total de la zona del footer
    header_gap  = 0.4 * cm      # separación visual entre header y contenido
    footer_gap  = 0.3 * cm      # separación visual entre contenido y footer

    # ── Margen del contenedor del contenido ──────────────────────── 
    top_margin    = header_h + header_gap
    bottom_margin = footer_h + footer_gap
    usable_w      = page_w - 2 * side_margin

    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        leftMargin=side_margin,
        rightMargin=side_margin,
        topMargin=top_margin,
        bottomMargin=bottom_margin,
    )

    # ── Story para construcción del documento ───────────────────────
    story = []

    # ==========================================================
    # Header y Footer
    # ==========================================================

    # ── Header ───────────────────────────────────────────
    def draw_header(canvas_obj, doc_obj):
        canvas_obj.saveState()

        header_top    = page_h                           # borde superior del header
        header_bottom = page_h - header_h                # borde inferior del header
        header_mid_y  = (header_top + header_bottom) / 2 # centro vertical del header

        # ── Logo izquierda ─────────────────────────────────────
        logo_h = 1.6 * cm
        pil_logo = Image.open(LOGO_PATH)
        logo_orig_w, logo_orig_h = pil_logo.size
        logo_aspect = logo_orig_w / logo_orig_h

        logo_w = logo_h * logo_aspect            # ancho proporcional
        logo_x = side_margin                     # alineado al margen izquierdo
        logo_y = header_mid_y - logo_h / 2       # centrado verticalmente en el header

        try:
            canvas_obj.drawImage(
                LOGO_PATH,
                x=logo_x,
                y=logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",                # respeta canal alpha del PNG
            )
        except Exception:
            pass                            # si el logo no existe, omitir

        # ── Texto derecha ──────────────────────────────────────
        line1 = "Visor de Exposición a la Amenaza de Incendios Forestales"
        line2 = "Ministerio de Desarrollo Social y Familia"
        text_x = page_w - side_margin     # alineado al margen derecho

        # Texto línea 1
        canvas_obj.setFont("Helvetica-Bold", 8)
        canvas_obj.setFillColor(colors.HexColor('#1A3C6E'))
        canvas_obj.drawRightString(
            text_x,
            header_mid_y + 0.15 * cm,
            line1,
        )

        # Texto línea 2
        canvas_obj.setFont("Helvetica", 7)
        canvas_obj.setFillColor(colors.HexColor('#6B7280'))
        canvas_obj.drawRightString(
            text_x,
            header_mid_y - 0.25 * cm,
            line2,
        )

        # ── Línea separadora  ───────────────────────────────────
        line_y = header_bottom - 0.10 * cm
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            side_margin,
            line_y,
            page_w - side_margin,
            line_y
        )

        canvas_obj.restoreState()

    # ── Footer ───────────────────────────────────────────
    def draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()

        footer_top    = footer_h           # borde superior del footer
        footer_y_text = footer_h / 2       # posición Y del texto de página

        # ── Línea separadora ──────────────────────────────
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            side_margin,
            footer_top,
            page_w - side_margin,
            footer_top,
        )

        # ── Número de página ───────────────────────────────────
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 8)
        canvas_obj.setFillColor(colors.HexColor('#6B7280'))
        canvas_obj.drawRightString(
            page_w - side_margin,
            footer_y_text,
            f"Página {page_num}",
        )

        canvas_obj.restoreState()

    # ── Header y Footer juntos ────────────────────────────────────
    def draw_header_footer(canvas_obj, doc_obj):
        draw_header(canvas_obj, doc_obj)
        draw_footer(canvas_obj, doc_obj)

    # ==========================================================
    # Añadir Títulos
    # ==========================================================

    # ── Título principal ────────────────────────────────────
    story.append(Paragraph(
        "<b>Visor de Exposición a la Amenaza de Incendios Forestales</b>",
        title_style
    ))
    story.append(Spacer(1, 0.4 * cm))

    # ── Título para el mapa ─────────────────────────────────
    story.append(Paragraph(
        "Mapa exposición a incendios del proyecto",
        map_title_style
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ==========================================================
    # Añadir imagen del mapa
    # ==========================================================

    # ── Dimensiones de la imagen ────────────────────────────────
    map_box_size = usable_w

    img_w, img_h = map_image.size
    side   = min(img_w, img_h)
    left   = (img_w - side) // 2
    top    = (img_h - side) // 2
    right  = left + side
    bottom = top  + side
    map_cropped = map_image.crop((left, top, right, bottom))

    # ── Cargar imagen del mapa ─────────────────────────────────
    img_buf = BytesIO()
    map_cropped.save(img_buf, format="PNG", dpi=(150, 150))
    img_buf.seek(0)

    # ── Crear contorno alrededor de la imagen ──────────────────
    rl_img = RLImage(img_buf, width=map_box_size, height=map_box_size)
    rl_img_container = [[rl_img]]
    rl_img_table = Table(rl_img_container)
    rl_img_table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#000000")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))

    story.append(rl_img_table)
    story.append(Spacer(1, 0.3 * cm))

    # ==========================================================
    # Añadir leyenda exposición de incendios (Tabla)
    # ==========================================================

    legend_items_data = [
        ("Bajo",     colors.HexColor('#AACEAC')),
        ("Medio",    colors.HexColor('#F1FB7B')),
        ("Alto",     colors.HexColor('#F7A248')),
        ("Muy Alto", colors.HexColor('#F0261C')),
    ]

    # ── Dimensiones leyenda ─────────────────────────────────
    color_box_size = 0.55 * cm          # lado del cuadrado de color
    col_gap        = 0.22 * cm          # espacio entre cuadrado y etiqueta
    row0_h         = 0.55 * cm          # alto de la fila del título
    row1_h         = 1 * cm             # alto de la fila de ítems
    item_col_w     = (usable_w / 4) / 1.4  # ancho equitativo para cada ítem

    # ── Fila 0 de la tabla: título "Exposición" ────────────────
    row0 = [Paragraph("Exposición", legend_title_style)] + [""] * (4 - 1)

    def make_item_cell(label: str, box_color) -> Table:
        # ── Crear micro tabla 1×2: [ cuadrado de color ] [ etiqueta de texto ] ────

        color_cell = ""                                        # El color del cuadrado se verá con TableStyle
        text_cell  = Paragraph(label, legend_label_style)     # Etiqueta de texto

        box_col_w  = color_box_size                            # Ancho disponible para el cuadrado de color
        text_col_w = item_col_w - color_box_size - col_gap     # Ancho disponible para el texto

        inner = Table(
            [[color_cell, text_cell]],
            colWidths=[box_col_w, text_col_w],
            rowHeights=[color_box_size],
        )

        # ── Estilo para el cuadrado de color ──────────────────────────
        inner.setStyle(TableStyle([
            # Color de fondo del cuadrado
            ("BACKGROUND",    (0, 0), (0, 0), box_color),
            # Borde fino del cuadrado
            ("BOX",           (0, 0), (0, 0), 0.5, colors.HexColor('#282828')),
            # Alineación vertical centrada en toda la micro tabla
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            # Padding cero en el cuadrado
            ("LEFTPADDING",   (0, 0), (0, 0), 0),
            ("RIGHTPADDING",  (0, 0), (0, 0), 0),
            ("TOPPADDING",    (0, 0), (0, 0), 0),
            ("BOTTOMPADDING", (0, 0), (0, 0), 0),
            # Padding izquierdo en la etiqueta (separa el cuadrado)
            ("LEFTPADDING",   (1, 0), (1, 0), col_gap),
            ("RIGHTPADDING",  (1, 0), (1, 0), 0),
            ("TOPPADDING",    (1, 0), (1, 0), 0),
            ("BOTTOMPADDING", (1, 0), (1, 0), 0),
        ]))

        return inner

    # ── Fila 1 de la tabla: ítems (cuadrado de color + etiqueta) ──────────────────
    row1 = [make_item_cell(label, color) for label, color in legend_items_data]

    # ── Crear tabla leyenda de 2 filas ─────────────────────────────────
    legend_table = Table(
        [row0, row1],
        colWidths=[item_col_w] * 4,
        rowHeights=[row0_h, row1_h],
        hAlign='LEFT'
    )

    legend_table.setStyle(TableStyle([
        # Alineación vertical centrada en todas las celdas
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        # Sin padding en ninguna celda de la tabla principal
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    story.append(legend_table)

    # ==========================================================
    # Construir PDF final con header y footer
    # ==========================================================

    doc.build(
        story,
        onFirstPage=draw_header_footer,
        onLaterPages=draw_header_footer,
    )
    buffer.seek(0)

    return buffer.read()