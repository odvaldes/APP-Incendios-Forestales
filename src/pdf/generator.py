from io import BytesIO
from PIL import Image
from datetime import datetime
from zoneinfo import ZoneInfo

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Spacer, Image as RLImage, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from config.constants import LOGO_PATH, INTERPRETATIONS


def generate_pdf(map_image: Image.Image, addr_poly: str, expo_result: dict, final_comments: str):

    # ==========================================================
    # Dimensiones del documento
    # ==========================================================

    buffer = BytesIO()
    today  = datetime.now(ZoneInfo("America/Santiago"))

    page_w, page_h = letter     # ancho y altura total del documento
    side_margin    = 2.5 * cm   # margen de los lados
    header_h       = 2 * cm     # altura total de la zona del header
    footer_h       = 2 * cm     # altura total de la zona del footer
    header_gap     = 0.4 * cm   # separación visual entre header y contenido
    footer_gap     = 0.3 * cm   # separación visual entre contenido y footer

    # -- Margen del contenedor del contenido ------------------------
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

    # ==========================================================
    # Estilos de texto
    # ==========================================================

    # -- Títulos -----------------------------------------------
    title_style = ParagraphStyle(
        name="TituloPrincipal",
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_CENTER,
        spaceAfter=0,
        spaceBefore=0,
        leading=22,
    )

    addr_title_style = ParagraphStyle(
        name="TituloDireccion",
        fontName="Helvetica-Bold",
        fontSize=16,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_CENTER,
        spaceAfter=4,
        spaceBefore=0,
        leading=19,
    )

    sub_title_style = ParagraphStyle(
        name="TituloSecundario",
        fontName="Helvetica-Bold",
        fontSize=15,
        textColor=colors.HexColor('#1A3C6E'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=17,
    )

    date_title_style = ParagraphStyle(
        name="TituloFecha",
        fontName="Helvetica",
        fontSize=11,
        textColor=colors.HexColor('#1A1A1A'),
        alignment=TA_CENTER,
        spaceAfter=4,
        spaceBefore=0,
        leading=14,
    )

    caption_title_style = ParagraphStyle(
        name="TituloCaption",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor('#1A1A1A'),
        alignment=TA_LEFT,
        spaceAfter=4,
        spaceBefore=0,
        leading=12,
    )

    # -- Contenido ---------------------------------------------
    badge_text_style = ParagraphStyle(
        name='TextoBadge',
        fontName='Helvetica-Bold',
        fontSize=10,
        textColor=colors.white,
        alignment=1,
    )

    comment_text_style = ParagraphStyle(
        name="TextoComentarios",
        fontName="Helvetica",
        fontSize=10,
        textColor=colors.HexColor("#0A0A0A"),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=14,
    )

    # -- Leyenda del mapa --------------------------------------
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

    # -- Anexo -------------------------------------------------
    annex_text_style = ParagraphStyle(
        name="TextoAnexo",
        fontName="Helvetica",
        fontSize=9,
        textColor=colors.HexColor('#1A1A1A'),
        alignment=TA_LEFT,
        spaceAfter=0,
        spaceBefore=0,
        leading=12,
    )

    # ==========================================================
    # Colores y función badge
    # ==========================================================

    colors_badge = {
        "Bajo":     colors.HexColor("#2E7D32"),
        "Medio":    colors.HexColor("#F9A825"),
        "Alto":     colors.HexColor("#Ef6C00"),
        "Muy Alto": colors.HexColor("#F00E02"),
        "Sin Dato": colors.HexColor("#9CA3AF"),
    }

    def create_badge(nivel):
        # -- Definir color de fondo y texto ----------------------
        color_background = colors_badge.get(nivel)
        badge_text = Paragraph(nivel, badge_text_style)

        # -- Crear mini tabla 1x1 para el badge ------------------
        badge_table = Table([[badge_text]], colWidths=[70], cornerRadii=[10, 10, 10, 10])

        # -- Aplicar diseño --------------------------------------
        badge_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), color_background),
            ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 8),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 8),
        ]))

        return badge_table

    # ==========================================================
    # Datos de niveles de exposición: nivel + interpretación
    # ==========================================================

    interpre_expo = [
        (nivel, INTERPRETATIONS[nivel]["text"])
        for nivel in ["Bajo", "Medio", "Alto", "Muy Alto", "Sin Dato"]
    ]

    # ==========================================================
    # Header y Footer
    # ==========================================================

    # -- Header ------------------------------------------------
    def draw_header(canvas_obj, doc_obj):
        canvas_obj.saveState()

        header_top    = page_h                            # borde superior del header
        header_bottom = page_h - header_h                 # borde inferior del header
        header_mid_y  = (header_top + header_bottom) / 2  # centro vertical del header

        # -- Logo izquierda -------------------------------------
        logo_h      = 1.6 * cm
        pil_logo    = Image.open(LOGO_PATH)
        logo_orig_w, logo_orig_h = pil_logo.size
        logo_aspect = logo_orig_w / logo_orig_h

        logo_w = logo_h * logo_aspect        # ancho proporcional
        logo_x = side_margin                 # alineado al margen izquierdo
        logo_y = header_mid_y - logo_h / 2  # centrado verticalmente en el header

        try:
            canvas_obj.drawImage(
                LOGO_PATH,
                x=logo_x,
                y=logo_y,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",            # respeta canal alpha del PNG
            )
        except Exception:
            pass                        # si el logo no existe, omitir

        # -- Texto derecha --------------------------------------
        line1  = "División de Evaluación Social de Inversiones — SNI"
        line2  = "Ministerio de Desarrollo Social y Familia"
        text_x = page_w - side_margin  # alineado al margen derecho

        # Texto línea 1
        canvas_obj.setFont("Helvetica-Bold", 7.5)
        canvas_obj.setFillColor(colors.HexColor('#1A3C6E'))
        canvas_obj.drawRightString(text_x, header_mid_y + 0.10 * cm, line1)

        # Texto línea 2
        canvas_obj.setFont("Helvetica", 7.5)
        canvas_obj.setFillColor(colors.HexColor('#555555'))
        canvas_obj.drawRightString(text_x, header_mid_y - 0.25 * cm, line2)

        # -- Línea separadora -----------------------------------
        line_y = header_bottom - 0.10 * cm
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(side_margin, line_y, page_w - side_margin, line_y)

        canvas_obj.restoreState()

    # -- Footer ------------------------------------------------
    def draw_footer(canvas_obj, doc_obj):
        canvas_obj.saveState()

        footer_top    = footer_h       # borde superior del footer
        footer_y_text = footer_h / 2  # posición Y del texto de página

        # -- Línea separadora -----------------------------------
        canvas_obj.setStrokeColor(colors.HexColor('#D1D5DB'))
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(side_margin, footer_top, page_w - side_margin, footer_top)

        # -- Número de página -----------------------------------
        page_num = canvas_obj.getPageNumber()
        canvas_obj.setFont("Helvetica", 10)
        canvas_obj.setFillColor(colors.HexColor('#6B7280'))
        canvas_obj.drawRightString(page_w - side_margin, footer_y_text, f"Página {page_num}")

        canvas_obj.restoreState()

    # -- Header y Footer juntos --------------------------------
    def draw_header_footer(canvas_obj, doc_obj):
        draw_header(canvas_obj, doc_obj)
        draw_footer(canvas_obj, doc_obj)

    # -- Story para construcción del documento -----------------------
    story = []

    # ==========================================================
    # PÁGINA 1 — Resultados del análisis
    # ==========================================================

    # -- Título principal ------------------------------------
    story.append(Paragraph(
        "<b>Exposición a la Amenaza de Incendios Forestales</b>",
        title_style
    ))
    story.append(Spacer(1, 0.1 * cm))

    # -- Dirección proyecto ----------------------------------
    story.append(Paragraph(addr_poly, addr_title_style))
    story.append(Spacer(1, 0.1 * cm))

    # -- Fecha reporte ---------------------------------------
    story.append(Paragraph(
        today.strftime("<b>Fecha de generación del reporte:</b> %d/%m/%Y"),
        date_title_style
    ))
    story.append(Spacer(1, 0.6 * cm))

    # -- Resultado exposición --------------------------------
    story.append(Paragraph("Nivel de exposición emplazamiento", sub_title_style))
    story.append(Spacer(1, 0.3 * cm))

    # -- Crear la tabla para mostrar la exposición a incendios -----
    layers_analyzed = Paragraph("<br/>".join(expo_result["layer"]))
    celda_badge     = create_badge(expo_result["dominante"])

    expo_data  = [
        ["Región analizada", "Nivel de exposición"],
        [layers_analyzed,    celda_badge],
    ]
    col_expo_w = usable_w / 2 - side_margin
    table_expo = Table(expo_data, colWidths=[col_expo_w, col_expo_w])

    # -- Aplicar diseño a la tabla de exposición a incendios --------
    table_expo.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (1, 0),  colors.HexColor('#1A5276')),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),  # Texto blanco para la primera fila
        # Todo el texto de la primera fila a la izquierda
        ('ALIGN',      (0, 0), (-1, 0), 'LEFT'),
        # Contenido de la celda (2, 1) a la izquierda y arriba
        ('ALIGN',      (0, 1), (0, 1),  'LEFT'),
        ('VALIGN',     (0, 1), (0, 1),  'TOP'),
        # Contenido de la celda (2, 2) en el centro
        ('ALIGN',      (1, 1), (1, 1),  'CENTER'),
        ('VALIGN',     (1, 1), (1, 1),  'MIDDLE'),
        ('FONTNAME',      (0, 0), (1, 0),  'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('BACKGROUND',    (0, 1), (-1, -1), colors.white),
        ('GRID',          (0, 0), (-1, -1), 1, colors.HexColor('#CCCCCC')),
    ]))

    story.append(table_expo)
    story.append(Spacer(1, 0.7 * cm))

    # -- Interpretación del nivel de exposición --------------
    story.append(Paragraph("Interpretación nivel de exposición", sub_title_style))
    story.append(Spacer(1, 0.2 * cm))

    # Obtener la interpretación según el nivel de exposición resultante
    nivel_exposicion   = expo_result["dominante"]
    interpretacion_text = next(
        (texto for nivel, texto in interpre_expo if nivel == nivel_exposicion),
        "Información no disponible."
    )

    interpretation_data  = [[Paragraph(interpretacion_text, comment_text_style)]]
    table_interpretation = Table(interpretation_data, colWidths=[usable_w], cornerRadii=[6, 6, 6, 6])

    # -- Aplicar diseño a la tabla de interpretación ----------------
    table_interpretation.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F7FBFF')),
        ('TEXTCOLOR',  (0, 0), (0, 0), colors.black),
        ('ALIGN',      (0, 0), (0, 0), 'LEFT'),
        ('VALIGN',     (0, 0), (0, 0), 'TOP'),
        ('FONTNAME',      (0, 0), (0, 0), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID',          (0, 0), (0, 0),   1, colors.HexColor('#C7D8E6')),
    ]))

    story.append(table_interpretation)
    story.append(Spacer(1, 0.7 * cm))

    # -- Comentarios finales del análisis --------------------
    story.append(Paragraph("Comentarios finales del análisis", sub_title_style))
    story.append(Spacer(1, 0.2 * cm))

    # Si no hay comentario guardado o está vacío → mostrar texto por defecto
    comments_text = final_comments.strip() if final_comments and final_comments.strip() else "Sin comentarios"
    comments_pdf  = comments_text.replace("\n", "<br/>")
    comments_data = [[Paragraph(comments_pdf, comment_text_style)]]
    table_comments = Table(comments_data, colWidths=[usable_w], cornerRadii=[6, 6, 6, 6])

    # -- Aplicar diseño a la tabla de comentarios finales --------
    table_comments.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#F7FBFF')),
        ('TEXTCOLOR',  (0, 0), (0, 0), colors.black),
        ('ALIGN',      (0, 0), (0, 0), 'LEFT'),
        ('VALIGN',     (0, 0), (0, 0), 'TOP'),
        ('FONTNAME',      (0, 0), (0, 0), 'Helvetica'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('GRID',          (0, 0), (0, 0),   1, colors.HexColor('#C7D8E6')),
    ]))

    story.append(table_comments)

    # -- Salto a la siguiente hoja -----------------------------
    story.append(PageBreak())

    # ==========================================================
    # PÁGINA 2 — Mapa de exposición
    # ==========================================================

    # -- Título para el mapa -----------------------------------
    story.append(Paragraph("Mapa exposición a incendios del proyecto", sub_title_style))
    story.append(Spacer(1, 0.3 * cm))

    # -- Dimensiones de la imagen --------------------------------
    map_box_size = usable_w

    img_w, img_h = map_image.size
    side   = min(img_w, img_h)
    left   = (img_w - side) // 2
    top    = (img_h - side) // 2
    right  = left + side
    bottom = top  + side
    map_cropped = map_image.crop((left, top, right, bottom))

    # -- Cargar imagen del mapa ---------------------------------
    img_buf = BytesIO()
    map_cropped.save(img_buf, format="PNG", dpi=(150, 150))
    img_buf.seek(0)

    # -- Crear contorno alrededor de la imagen ------------------
    rl_img           = RLImage(img_buf, width=map_box_size, height=map_box_size)
    rl_img_container = [[rl_img]]
    rl_img_table     = Table(rl_img_container)

    rl_img_table.setStyle(TableStyle([
        ('BOX',           (0, 0), (-1, -1), 1, colors.HexColor("#000000")),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
        ('TOPPADDING',    (0, 0), (-1, -1), 0),
        ('LEFTPADDING',   (0, 0), (-1, -1), 0),
        ('RIGHTPADDING',  (0, 0), (-1, -1), 0),
    ]))

    story.append(rl_img_table)
    story.append(Spacer(1, 0.3 * cm))

    # -- Leyenda de exposición ----------------------------------
    legend_items_data = [
        ("Bajo",     colors.HexColor('#AACEAC')),
        ("Medio",    colors.HexColor('#F1FB7B')),
        ("Alto",     colors.HexColor('#F7A248')),
        ("Muy Alto", colors.HexColor('#F0261C')),
    ]

    # -- Dimensiones leyenda ------------------------------------
    color_box_size = 0.55 * cm          # lado del cuadrado de color
    col_gap        = 0.22 * cm          # espacio entre cuadrado y etiqueta
    row0_h         = 0.55 * cm          # alto de la fila del título
    row1_h         = 1 * cm             # alto de la fila de ítems
    item_col_w     = (usable_w / 4) / 1.4  # ancho equitativo para cada ítem

    # -- Fila 0 de la tabla: título "Exposición" ----------------
    row0 = [Paragraph("Exposición", legend_title_style)] + [""] * (4 - 1)

    def make_item_cell(label: str, box_color) -> Table:
        # -- Crear micro tabla 1×2: [ cuadrado de color ] [ etiqueta de texto ] ----

        color_cell = ""                                         # El color del cuadrado se verá con TableStyle
        text_cell  = Paragraph(label, legend_label_style)      # Etiqueta de texto

        box_col_w  = color_box_size                             # Ancho disponible para el cuadrado de color
        text_col_w = item_col_w - color_box_size - col_gap      # Ancho disponible para el texto

        inner = Table(
            [[color_cell, text_cell]],
            colWidths=[box_col_w, text_col_w],
            rowHeights=[color_box_size],
        )

        # -- Estilo para el cuadrado de color --------------------------
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

    # -- Fila 1 de la tabla: ítems (cuadrado de color + etiqueta) ------------------
    row1 = [make_item_cell(label, color) for label, color in legend_items_data]

    # -- Crear tabla leyenda de 2 filas ---------------------------------
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

    # -- Salto a la tercera página para el anexo ---------------
    story.append(PageBreak())

    # ==========================================================
    # PÁGINA 3 — Anexo: Simbología y niveles de exposición
    # ==========================================================

    # -- Título del anexo ---------------------------------------
    story.append(Paragraph("Anexo: Simbología y niveles de exposición", sub_title_style))
    story.append(Spacer(1, 0.2 * cm))

    # -- Anchos de columnas de la tabla del anexo ---------------
    col_badge_w          = 3.8 * cm                    # columna del badge
    col_interpretation_w = usable_w - col_badge_w      # columna de interpretación

    # -- Construir filas de la tabla ----------------------------
    annex_data = [["Nivel de exposición", "Interpretación"]]
    for nivel, interpretacion in interpre_expo:
        annex_data.append([
            create_badge(nivel),
            Paragraph(interpretacion, annex_text_style),
        ])

    # -- Crear tabla del anexo ----------------------------------
    annex_table = Table(
        annex_data,
        colWidths=[col_badge_w, col_interpretation_w],
        hAlign='LEFT',
    )

    # -- Aplicar diseño a la tabla del anexo --------------------
    annex_table.setStyle(TableStyle([
        # Encabezado
        ('BACKGROUND',    (0, 0), (-1, 0), colors.HexColor('#1A5276')),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN',         (0, 0), (-1, 0), 'LEFT'),
        ('VALIGN',        (0, 0), (-1, 0), 'MIDDLE'),
        ('TOPPADDING',    (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
        ('LEFTPADDING',   (0, 0), (-1, 0), 8),
        ('RIGHTPADDING',  (0, 0), (-1, 0), 8),

        # Filas de datos
        ('VALIGN',        (0, 1), (-1, -1), 'MIDDLE'),
        ('ALIGN',         (0, 1), (0, -1),  'CENTER'),   # badges centrados
        ('ALIGN',         (1, 1), (1, -1),  'LEFT'),     # texto alineado izquierda
        ('TOPPADDING',    (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('LEFTPADDING',   (1, 1), (1, -1),  8),
        ('RIGHTPADDING',  (1, 1), (1, -1),  8),

        # Filas alternas para mejor legibilidad
        ('BACKGROUND',    (0, 1), (-1, 1), colors.HexColor('#FFFFFF')),
        ('BACKGROUND',    (0, 2), (-1, 2), colors.HexColor('#F4F6F7')),
        ('BACKGROUND',    (0, 3), (-1, 3), colors.HexColor('#FFFFFF')),
        ('BACKGROUND',    (0, 4), (-1, 4), colors.HexColor('#F4F6F7')),
        ('BACKGROUND',    (0, 5), (-1, 5), colors.HexColor('#FFFFFF')),

        # Bordes
        ('GRID',          (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
        ('LINEBELOW',     (0, 0), (-1, 0),  1,   colors.HexColor('#1A5276')),
    ]))

    story.append(annex_table)

    # -- Nota al pie del anexo ----------------------------------
    story.append(Spacer(1, 0.2 * cm))
    story.append(Paragraph(
        "<b>Nota:</b> La exposición se determina por el nivel de exposición de mayor riesgo "
        "encontrado dentro del área de análisis (polígono original + buffer de 100 m).",
        caption_title_style
    ))

    # ==========================================================
    # Construir PDF final con header y footer
    # ==========================================================

    doc.build(
        story,
        onFirstPage=draw_header_footer,
        onLaterPages=draw_header_footer,
    )
    buffer.seek(0)

    pdf_name = today.strftime("reporte_exposicion_incendio-%Y-%m-%d_%H%M.pdf")

    return buffer.read(), pdf_name