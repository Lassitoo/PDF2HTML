# documents/utils/pdf_processor.py
import base64
import io
from datetime import datetime
from django.utils import timezone

# Gestion des imports avec fallback
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

# OCR (optionnel)
try:
    import pytesseract

    # Ajuste si besoin le chemin Windows :
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    from PIL import Image
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False


class PDFProcessor:
    """Processeur PDF qui reproduit EXACTEMENT la structure originale avec tableaux corrigés"""
    # Ne jamais reconstruire de tableaux synthétiques si la grille vectorielle n'existe pas
    RECONSTRUCT_IF_NO_GRID = False

    def __init__(self):
        # Pas de facteur d'échelle - on garde les coordonnées PDF exactes
        self.scale_factor = 1.0

    def process(self, file_path, document_instance):
        """Traite un fichier PDF en conservant la structure EXACTE"""
        try:
            print(f"Début traitement PDF structural: {file_path}")

            if PYMUPDF_AVAILABLE:
                return self._process_with_exact_structure(file_path, document_instance)
            elif PDFPLUMBER_AVAILABLE:
                return self._process_with_pdfplumber_simple(file_path)
            else:
                return self._process_basic_fallback(file_path)

        except Exception as e:
            print(f"Erreur traitement PDF: {str(e)}")
            import traceback
            traceback.print_exc()
            return self._process_basic_fallback_with_message(f"Erreur: {str(e)}")

    def _process_with_exact_structure(self, file_path, document_instance):
        """Reproduction EXACTE de la structure PDF avec tableaux intelligents"""
        doc = None
        try:
            print("Ouverture PDF pour structure exacte...")
            doc = fitz.open(file_path)

            if len(doc) == 0:
                raise ValueError("Document PDF vide")

            metadata = doc.metadata or {}
            content = ""
            formatted_content = ""
            images = []
            fonts_used = set()

            # Traiter chaque page avec structure exacte et tableaux intelligents
            for page_num in range(len(doc)):
                try:
                    print(f"Traitement structural page {page_num + 1}...")
                    page = doc[page_num]

                    page_content, page_html, page_images, page_fonts = self._process_page_with_smart_tables(
                        page, page_num
                    )

                    content += f"\n--- Page {page_num + 1} ---\n{page_content}\n"
                    formatted_content += page_html
                    images.extend(page_images)
                    fonts_used.update(page_fonts)

                    print(f"Page {page_num + 1}: {len(page_content)} caractères, {len(page_images)} images")

                except Exception as e:
                    print(f"Erreur page {page_num + 1}: {str(e)}")
                    continue

            # Dimensions de la première page (coordonnées PDF exactes)
            first_page = doc[0] if len(doc) > 0 else None
            page_width = first_page.rect.width if first_page else 595
            page_height = first_page.rect.height if first_page else 842

            doc.close()
            doc = None

            if not content.strip():
                return self._process_basic_fallback_with_message("Aucun contenu extrait")

            result = {
                'content': content,
                'formatted_content': f'<div class="pdf-document-exact">{formatted_content}</div>',
                'author': metadata.get('author', ''),
                'creation_date': self._parse_pdf_date(metadata.get('creationDate')),
                'modification_date': self._parse_pdf_date(metadata.get('modDate')),
                'images': images,
                'format_info': {
                    'page_width': page_width,
                    'page_height': page_height,
                    'fonts_used': list(fonts_used),
                    'has_images': len(images) > 0,
                    'has_tables': self._detect_tables_in_content(content),
                    'has_headers': False,
                    'has_footers': False,
                    'generated_css': self._generate_improved_css()
                }
            }

            print("Structure exacte générée avec succès")
            return result

        except Exception as e:
            print(f"Erreur structure exacte: {str(e)}")
            if doc:
                try:
                    doc.close()
                except:
                    pass
            return self._process_basic_fallback_with_message(f"Erreur: {str(e)}")

    # --------------------------
    # OCR: heuristique & helper
    # --------------------------
    def _should_ocr(self, elements, min_chars=30):
        """Heuristique simple : s'il y a très peu de texte natif, on tente l'OCR."""
        total_chars = sum(len(e.get("text", "")) for e in elements)
        return total_chars < min_chars

    def _ocr_page_to_elements(self, page, dpi=300, lang="eng+fra"):
        """
        Convertit la page en image, passe l'OCR, et retourne une liste d'éléments
        positionnés compatibles avec _extract_all_positioned_elements.
        """
        if not OCR_AVAILABLE:
            return []

        try:
            # Rendu bitmap haute def de la page (72dpi -> dpi)
            scale = dpi / 72.0
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)

            # Choix du mode selon le nombre de canaux
            mode = "RGB" if getattr(pix, "n", 3) >= 3 else "L"
            img = Image.frombytes(mode, [pix.width, pix.height], pix.samples)
            if mode == "L":
                img = img.convert("RGB")

            # OCR au niveau "word" pour récupérer des bbox fines
            data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

            elements = []
            element_id = 0

            # Échelle image -> coordonnées PDF
            w_scale = page.rect.width / float(pix.width or 1)
            h_scale = page.rect.height / float(pix.height or 1)

            for i in range(len(data.get("text", []))):
                text = (data["text"][i] or "").strip()
                conf_raw = data.get("conf", ["-1"] * len(data["text"]))[i]
                try:
                    conf = float(conf_raw)
                except:
                    conf = -1.0

                if not text or conf < 60:  # filtre mots OCR peu fiables
                    continue

                x = float(data["left"][i]) * w_scale
                y = float(data["top"][i]) * h_scale
                w = float(data["width"][i]) * w_scale
                h = float(data["height"][i]) * h_scale

                elements.append({
                    "id": element_id,
                    "text": text,
                    "bbox": (x, y, x + w, y + h),
                    "x0": x, "y0": y, "x1": x + w, "y1": y + h,
                    "font": "OCR",
                    "size": max(8, min(12, h * 0.9)),  # taille approx pour lisibilité
                    "flags": 0,
                    "color": 0,
                })
                element_id += 1

            return elements
        except Exception as e:
            print(f"OCR failed: {e}")
            return []

    def _process_page_with_smart_tables(self, page, page_num):
        """Traite une page avec détection intelligente des tableaux sans reconstruire
        de sous-tableaux: on ne 'snap' que sur les grilles vectorielles existantes.
        Si la page n'a pas de texte (scan), fallback OCR pour obtenir du texte sélectionnable.
        """
        page_rect = page.rect
        page_width = page_rect.width
        page_height = page_rect.height

        print(f"  Traitement intelligent page {page_num + 1}: {page_width} x {page_height}")

        content = ""
        images = []
        fonts = set()
        ocr_used = False

        page_html = f'''
        <div class="pdf-page-exact" data-page="{page_num + 1}" style="
            position: relative;
            width: {page_width}px;
            height: {page_height}px;
            margin: 20px auto;
            background: white;
            border: 1px solid #ccc;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
            overflow: visible;
        ">
        '''

        try:
            # 1) Texte positionné natif
            text_dict = page.get_text("dict")
            all_elements = self._extract_all_positioned_elements(text_dict)

            # 1.b) Fallback OCR si (quasi) pas de texte natif
            if (not all_elements or self._should_ocr(all_elements)):
                ocr_elems = self._ocr_page_to_elements(page, dpi=300, lang="eng+fra")
                if ocr_elems:
                    print("  -> OCR utilisé (page sans couche texte ou très peu de texte).")
                    all_elements = ocr_elems
                    ocr_used = True

            # 2) Primitives vectorielles existantes (grilles / cadres)
            H, V, RECTS = self._collect_vector_primitives(page)

            # 3) Détection des zones susceptibles d'être des tableaux (via le texte)
            table_zones = self._detect_smart_table_zones(all_elements)

            processed_elements = set()
            grid_bboxes = []  # on accumule les zones où une grille vectorielle existe

            for zone in table_zones:
                # BBox de la zone
                min_x = min(e['x0'] for e in zone)
                max_x = max(e['x1'] for e in zone)
                min_y = min(e['y0'] for e in zone)
                max_y = max(e['y1'] for e in zone)
                zone_bbox = (min_x, min_y, max_x, max_y)

                # (A) Si une grille vectorielle existe -> 'snap' le texte dans les cellules
                if self._zone_has_vector_grid(zone_bbox, H, V, RECTS):
                    cell_html, consumed_ids = self._render_grid_cells_with_text(zone_bbox, zone, H, V)
                    page_html += cell_html
                    processed_elements.update(consumed_ids)
                    grid_bboxes.append(zone_bbox)
                    continue

                # (B) Reconstruction désactivée : NE PAS créer de <table> synthétique.
                #     Le texte de cette zone sera rendu plus bas en éléments absolus.

            # 4) Rendu du texte restant (éléments non consommés par le 'snap')
            remaining = [e for e in all_elements if e['id'] not in processed_elements]
            for element in remaining:
                elem_html = self._render_single_element(element, page_height)
                page_html += elem_html
                content += element['text'] + " "
                fonts.add(element.get('font', ''))

            # 5) Images
            #    Si OCR a été utilisé, NE PAS poser l'image plein-page (sinon elle peut recouvrir le texte).
            if not ocr_used:
                images = self._extract_images_with_positions(page, page_num, page_height)
                for image_data in images:
                    # Ignorer les images "fond de page" (pleine page)
                    if image_data.get('coverage', 0) >= 0.90:
                        continue
                    page_html += f'''
                    <img class="pdf-image-exact" 
                         src="data:image/{image_data['format']};base64,{image_data['base64']}" 
                         style="
                             position: absolute;
                             left: {image_data['x']}px;
                             top: {image_data['y']}px;
                             width: {image_data['width']}px;
                             height: {image_data['height']}px;
                             border: none;
                             z-index: 0;
                             pointer-events: none;
                         "
                         alt="{image_data['name']}" />
                    '''
            else:
                # (facultatif) Image de fond très légère — désactivée par défaut
                pass

            # 6) Repeindre les grilles/cadres vectoriels en filtrant les rectangles internes aux grilles
            page_html += self._render_drawings(page, grid_bboxes)

        except Exception as e:
            print(f"    Erreur traitement intelligent: {e}")
            return self._fallback_simple_extraction(page, page_num)

        page_html += '</div>'
        return content, page_html, images, fonts

    def _compute_grid_from_lines(self, bbox, H, V, tol=1.0):
        """
        Calcule les bords de colonnes/lignes à partir des segments H/V présents dans 'bbox'.
        Retourne (col_edges, row_edges) ordonnés.
        """
        x0, y0, x1, y1 = bbox
        H_in = [h for h in H if (y0 - tol <= h[1] <= y1 + tol) and (max(0, min(h[2], x1) - max(h[0], x0)) > 5)]
        V_in = [v for v in V if (x0 - tol <= v[0] <= x1 + tol) and (max(0, min(v[3], y1) - max(v[1], y0)) > 5)]

        x_candidates = [x0, x1] + [v[0] for v in V_in]
        y_candidates = [y0, y1] + [h[1] for h in H_in]
        x_candidates = sorted(set(round(x, 1) for x in x_candidates))
        y_candidates = sorted(set(round(y, 1) for y in y_candidates))

        def dedup(vals, eps=0.8):
            out = []
            for v in vals:
                if not out or abs(v - out[-1]) > eps:
                    out.append(v)
            return out

        col_edges = dedup(x_candidates)
        row_edges = dedup(y_candidates)
        if len(col_edges) < 2 or len(row_edges) < 2:
            return [], []
        return col_edges, row_edges

    def _render_grid_cells_with_text(self, bbox, zone_elements, H, V, padding=4):
        """
        Rend des wrappers <div> par cellule de la grille existante et repositionne
        les spans de 'zone_elements' à l'intérieur (snap).
        Retourne (html, consumed_ids).
        """
        html = []
        consumed_ids = set()

        col_edges, row_edges = self._compute_grid_from_lines(bbox, H, V)
        if not col_edges or not row_edges:
            return "", consumed_ids

        spans = [{
            "id": e["id"], "x0": e["x0"], "y0": e["y0"], "x1": e["x1"], "y1": e["y1"],
            "text": e["text"], "font": e["font"], "size": e["size"], "flags": e["flags"]
        } for e in zone_elements]

        def center(e):
            return ((e["x0"] + e["x1"]) / 2.0, (e["y0"] + e["y1"]) / 2.0)

        for r in range(len(row_edges) - 1):
            cy0, cy1 = row_edges[r], row_edges[r + 1]
            for c in range(len(col_edges) - 1):
                cx0, cx1 = col_edges[c], col_edges[c + 1]

                cell_x, cell_y = cx0, cy0
                cell_w = max(1, cx1 - cx0)
                cell_h = max(1, cy1 - cy0)

                cell_spans = []
                for e in spans:
                    if e["id"] in consumed_ids:
                        continue
                    cx, cy = center(e)
                    if (cx >= cx0 and cx <= cx1 and cy >= cy0 and cy <= cy1):
                        cell_spans.append(e)
                        consumed_ids.add(e["id"])

                # ⚠️ ne pas bloquer la sélection : PAS de pointer-events:none
                html.append(
                    f'<div class="pdf-cell" style="position:absolute;left:{cell_x}px;top:{cell_y}px;'
                    f'width:{cell_w}px;height:{cell_h}px;z-index:1;">'
                )

                for e in sorted(cell_spans, key=lambda s: (s["y0"], s["x0"])):
                    rel_left = max(padding, e["x0"] - cell_x)
                    rel_top = max(padding, e["y0"] - cell_y)
                    rel_w = max(1, e["x1"] - e["x0"])
                    rel_h = max(1, e["y1"] - e["y0"])
                    is_bold = bool(e["flags"] & 16)
                    fw = "bold" if is_bold else "normal"
                    html.append(
                        f'<div style="position:absolute;left:{rel_left}px;top:{rel_top}px;'
                        f'width:{rel_w}px;height:{rel_h}px;white-space:pre;line-height:1.1;'
                        f'font-family:\'{self._normalize_font(e["font"])}\', Times, serif;'
                        f'font-size:{e["size"]}px;font-weight:{fw};'
                        f'user-select:text;z-index:2;">'
                        f'{self._escape_html(e["text"])}</div>'
                    )

                html.append('</div>')

        return "".join(html), consumed_ids

    def _rect_inside_any(self, rect, bboxes, margin=0.8):
        """True si 'rect' est entièrement contenu dans au moins une bbox (avec marge)."""
        rx0, ry0, rx1, ry1 = rect
        for bx0, by0, bx1, by1 in bboxes:
            if (rx0 >= bx0 - margin and ry0 >= by0 - margin and
                    rx1 <= bx1 + margin and ry1 <= by1 + margin):
                return True
        return False

    def _extract_all_positioned_elements(self, text_dict):
        """Extrait tous les éléments avec leurs positions exactes"""
        elements = []
        element_id = 0

        for block in text_dict.get("blocks", []):
            if "lines" not in block:
                continue

        # NOTE: PyMuPDF renvoie les lignes avec leurs spans (coords PDF origin haut-gauche)
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    if not text:
                        continue

                    bbox = span.get("bbox")
                    if not bbox:
                        continue

                    elements.append({
                        'id': element_id,
                        'text': text,
                        'bbox': bbox,
                        'x0': bbox[0], 'y0': bbox[1], 'x1': bbox[2], 'y1': bbox[3],
                        'font': span.get("font", "Arial"),
                        'size': span.get("size", 12),
                        'flags': span.get("flags", 0),
                        'color': span.get("color", 0)
                    })
                    element_id += 1

        return elements

    def _detect_smart_table_zones(self, elements):
        """Détecte les zones qui contiennent des tableaux (seuils plus stricts)."""
        if not elements:
            return []

        # Tri visuel : haut -> bas
        sorted_elements = sorted(elements, key=lambda e: e['y0'])

        # Grouper en lignes approx.
        lines, current_line = [], []
        tolerance_y = 8

        for element in sorted_elements:
            if not current_line:
                current_line = [element]
            else:
                avg_y = sum(e['y0'] for e in current_line) / len(current_line)
                if abs(element['y0'] - avg_y) <= tolerance_y:
                    current_line.append(element)
                else:
                    current_line.sort(key=lambda e: e['x0'])
                    lines.append(current_line)
                    current_line = [element]
        if current_line:
            current_line.sort(key=lambda e: e['x0'])
            lines.append(current_line)

        # Séquences de lignes "table"
        table_zones, potential = [], []
        for line in lines:
            if self._is_smart_table_line(line):
                potential.append(line)
            else:
                if len(potential) >= 4:  # plus strict
                    tz = []
                    for pl in potential:
                        tz.extend(pl)
                    table_zones.append(tz)
                potential = []

        if len(potential) >= 4:
            tz = []
            for pl in potential:
                tz.extend(pl)
            table_zones.append(tz)

        return table_zones

    def _is_smart_table_line(self, line_elements):
        """Détection intelligente des lignes de tableau avec gestion des notes"""
        if len(line_elements) < 2:
            return False

        text_combined = " ".join(elem['text'] for elem in line_elements)

        # Exclure certaines longues notes de bas de page
        if len(text_combined) > 50 and (text_combined.startswith('1 ') or 'Ingredients of dry premix' in text_combined):
            return False

        criteria_met = 0

        if len(set(elem['x0'] for elem in line_elements)) >= 2:
            criteria_met += 1

        if any(char.isdigit() for char in text_combined):
            criteria_met += 1

        pharma_keywords = ['mg', 'agent', 'European', 'Pharmacopoeia', 'monograph', 'substance',
                           'Diluent', 'Lubricant', 'Binding', 'Flow', 'Disintegrant', 'Film-coating']
        if any(keyword in text_combined for keyword in pharma_keywords):
            criteria_met += 2

        if len(line_elements) >= 3:
            avg_text_length = sum(len(elem['text']) for elem in line_elements) / len(line_elements)
            if avg_text_length < 15:
                criteria_met += 1

        if len(line_elements) >= 3:
            spacings = []
            for i in range(1, len(line_elements)):
                spacing = line_elements[i]['x0'] - line_elements[i - 1]['x1']
                spacings.append(spacing)

            if spacings:
                avg_spacing = sum(spacings) / len(spacings)
                regular_spacings = sum(1 for s in spacings if abs(s - avg_spacing) < 25)
                if regular_spacings >= len(spacings) * 0.6:
                    criteria_met += 1

        return criteria_met >= 3

    def _reconstruct_smart_table(self, table_zone, page_height):
        """Reconstruit intelligemment un tableau HTML à partir d'une zone détectée"""
        if not table_zone:
            return "", ""

        # Calculer la bbox de la zone complète
        min_x = min(elem['x0'] for elem in table_zone)
        max_x = max(elem['x1'] for elem in table_zone)
        min_y = min(elem['y0'] for elem in table_zone)
        max_y = max(elem['y1'] for elem in table_zone)

        # Position CSS (origine en haut-gauche)
        css_left = min_x
        css_top = min_y
        css_width = max_x - min_x

        # Organiser les éléments en lignes avec tri correct
        rows = self._organize_elements_into_smart_rows(table_zone)
        if not rows:
            return "", ""

        # Analyser la structure des colonnes
        column_info = self._analyze_table_columns(rows)

        # Construire le HTML du tableau
        table_html = f'''
        <table class="pdf-table-smart" style="
            position: absolute;
            left: {css_left}px;
            top: {css_top}px;
            width: {css_width}px;
            border-collapse: collapse;
            border: 2px solid #333;
            background: white;
            font-family: 'Times New Roman', Times, serif;
            font-size: 9px;
            line-height: 1.2;
            z-index: 1;
        ">
        '''

        # Traiter chaque ligne avec logique intelligente
        table_content = ""
        for i, row in enumerate(rows):
            row_cells = self._extract_smart_row_cells(row, column_info)
            is_header = self._is_header_row_smart(row, i)
            tag = 'th' if is_header else 'td'

            table_html += '<tr>'
            for j, cell_text in enumerate(row_cells):
                cell_style = "border: 1px solid #333; padding: 4px; vertical-align: top; user-select:text;"

                if is_header:
                    cell_style += " font-weight: bold; background-color: #f0f0f0; text-align: center;"
                else:
                    if j == 0:
                        cell_style += " text-align: left; font-weight: 500;"
                    elif any(char.isdigit() for char in cell_text):
                        cell_style += " text-align: right;"
                    else:
                        cell_style += " text-align: left;"

                clean_text = cell_text.strip()
                table_html += f'<{tag} style="{cell_style}">{self._escape_html(clean_text)}</{tag}>'

            table_html += '</tr>'
            table_content += " | ".join(row_cells) + "\n"

        table_html += '</table>'

        return table_html, table_content

    def _organize_elements_into_smart_rows(self, table_zone):
        """Organise intelligemment les éléments en lignes"""
        if not table_zone:
            return []

        # Trier par Y croissant (haut -> bas), puis X croissant
        sorted_elements = sorted(table_zone, key=lambda e: (e['y0'], e['x0']))

        rows = []
        current_row = []
        tolerance_y = 6  # Tolérance réduite pour plus de précision

        for element in sorted_elements:
            if not current_row:
                current_row = [element]
            else:
                avg_y = sum(e['y0'] for e in current_row) / len(current_row)

                if abs(element['y0'] - avg_y) <= tolerance_y:
                    current_row.append(element)
                else:
                    current_row.sort(key=lambda e: e['x0'])
                    rows.append(current_row)
                    current_row = [element]

        if current_row:
            current_row.sort(key=lambda e: e['x0'])
            rows.append(current_row)

        return rows

    def _analyze_table_columns(self, rows):
        """Analyse la structure des colonnes du tableau"""
        all_x_positions = []

        for row in rows:
            for elem in row:
                all_x_positions.append(elem['x0'])

        unique_positions = sorted(set(all_x_positions))
        column_thresholds = []
        tolerance = 12

        for pos in unique_positions:
            found = False
            for i, threshold in enumerate(column_thresholds):
                if abs(pos - threshold) < tolerance:
                    column_thresholds[i] = (column_thresholds[i] + pos) / 2
                    found = True
                    break

            if not found:
                column_thresholds.append(pos)

        column_thresholds.sort()

        return {
            'thresholds': column_thresholds,
            'count': len(column_thresholds),
            'tolerance': tolerance
        }

    def _extract_smart_row_cells(self, row, column_info):
        """Extrait intelligemment les cellules d'une ligne"""
        thresholds = column_info['thresholds']
        tolerance = column_info['tolerance']
        cells = [''] * len(thresholds)

        for elem in row:
            elem_x = elem['x0']
            best_col = 0
            min_distance = abs(elem_x - thresholds[0])

            for j, threshold in enumerate(thresholds):
                distance = abs(elem_x - threshold)
                if distance < min_distance:
                    min_distance = distance
                    best_col = j

            if cells[best_col]:
                cells[best_col] += " " + elem['text']
            else:
                cells[best_col] = elem['text']

        return cells

    def _is_header_row_smart(self, row, row_index):
        """Détection intelligente des en-têtes de tableau"""
        if row_index == 0:
            return True

        bold_count = sum(1 for elem in row if elem['flags'] & 16)
        if bold_count >= len(row) * 0.6:
            return True

        text_combined = " ".join(elem['text'] for elem in row).lower()
        header_keywords = ['ingredients', 'amount', 'role', 'specification', 'mg']
        if any(keyword in text_combined for keyword in header_keywords):
            return True

        return False

    def _render_single_element(self, element, page_height):
        """Rendu d'un élément individuel avec gestion améliorée des notes"""
        css_left = element['x0']
        css_top = element['y0']  # origine en haut-gauche, plus d'inversion
        css_width = max(1, element['x1'] - element['x0'])
        css_height = max(1, element['y1'] - element['y0'])

        font_size = element['size']
        is_bold = bool(element['flags'] & 16)
        font_weight = 'bold' if is_bold else 'normal'

        # Détecter les notes de bas de page
        is_footnote = (
            font_size < 9 or
            str(element.get('text', '')).startswith('1 ') or
            'Ingredients of dry premix' in str(element.get('text', ''))
        )

        if is_footnote:
            font_size = max(7, font_size)  # Police minimale pour lisibilité
            return f'''
            <div class="pdf-footnote" style="
                position: absolute;
                left: {css_left}px;
                top: {css_top}px;
                width: {css_width}px;
                min-height: {css_height}px;
                font-family: '{self._normalize_font(element.get('font','Times New Roman'))}', Times, serif;
                font-size: {font_size}px;
                font-weight: {font_weight};
                line-height: 1.1;
                color: #666;
                white-space: pre;
                word-wrap: break-word;
                z-index: 2;
                user-select: text;
            ">{self._escape_html(element.get('text',''))}</div>
            '''

        # Détecter les titres par taille de police
        if font_size > 12:
            font_weight = 'bold'
        css_height = max(css_height, font_size * 1.2)

        return f'''
        <div class="pdf-text-element" style="
            position: absolute;
            left: {css_left}px;
            top: {css_top}px;
            width: {css_width}px;
            height: {css_height}px;
            font-family: '{self._normalize_font(element.get('font','Times New Roman'))}', Times, serif;
            font-size: {font_size}px;
            font-weight: {font_weight};
            line-height: 1.1;
            white-space: pre;
            overflow: visible;
            z-index: 2;
            user-select: text;
        ">{self._escape_html(element.get('text',''))}</div>
        '''

    def _extract_images_with_positions(self, page, page_num, page_height):
        """Extraction des images avec positions exactes"""
        images = []
        try:
            image_list = page.get_images()
            for img_index, img in enumerate(image_list):
                try:
                    image_rects = page.get_image_rects(img[0])
                    for rect in image_rects:
                        img_x0, img_y0, img_x1, img_y1 = rect.x0, rect.y0, rect.x1, rect.y1
                        css_left = img_x0
                        css_top = img_y0
                        css_width = img_x1 - img_x0
                        css_height = img_y1 - img_y0

                        # calcul de couverture pour éviter les pleines pages
                        page_w = page.rect.width
                        page_h = page.rect.height
                        coverage = (css_width * css_height) / float(max(1.0, page_w * page_h))

                        image_data = self._extract_image_data(page, img, page_num, img_index)
                        if image_data:
                            images.append({
                                **image_data,
                                'x': css_left,
                                'y': css_top,
                                'width': int(css_width),
                                'height': int(css_height),
                                'coverage': coverage
                            })
                except Exception as e:
                    print(f"      Erreur image {img_index}: {e}")
                    continue
        except Exception as e:
            print(f"    Erreur extraction images: {e}")

        return images

    def _render_drawings(self, page, grid_bboxes=None):
        """
        Rend les lignes/rectangles vectoriels.
        - Lignes ('l') : toujours rendues (délimitent la grille).
        - Rectangles ('re') : ignorés s'ils sont à l'intérieur d'une zone de grille détectée,
          pour éviter les cadres "sous-tableau".
        Les tracés sont placés en fond (z-index:0) et n'interceptent pas les événements.
        """
        if grid_bboxes is None:
            grid_bboxes = []

        html = []
        try:
            drawings = page.get_drawings()
        except Exception as e:
            print(f"    Erreur get_drawings(): {e}")
            return ""

        for d in drawings:
            items = d.get("items", [])
            for it in items:
                try:
                    if not it:
                        continue
                    cmd = it[0]

                    if cmd == "l":
                        if len(it) >= 3 and isinstance(it[1], (tuple, list)):
                            p1, p2 = it[1], it[2]
                            x0, y0 = float(p1[0]), float(p1[1])
                            x1, y1 = float(p2[0]), float(p2[1])
                        elif len(it) >= 5:
                            _, x0, y0, x1, y1 = it[:5]
                            x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
                        else:
                            continue

                        left = min(x0, x1)
                        top = min(y0, y1)
                        width = abs(x1 - x0)
                        height = abs(y1 - y0)

                        if height < 0.5:  # horizontale
                            html.append(
                                f'<div style="position:absolute;left:{left}px;top:{y0}px;'
                                f'width:{width}px;border-top:1px solid #333;z-index:0;pointer-events:none;"></div>'
                            )
                        elif width < 0.5:  # verticale
                            html.append(
                                f'<div style="position:absolute;left:{x0}px;top:{top}px;'
                                f'height:{height}px;border-left:1px solid #333;z-index:0;pointer-events:none;"></div>'
                            )

                    elif cmd == "re":
                        if len(it) >= 2 and hasattr(it[1], "x0"):
                            r = it[1]
                            x0, y0, x1, y1 = float(r.x0), float(r.y0), float(r.x1), float(r.y1)
                        elif len(it) >= 5:
                            _, x0, y0, x1, y1 = it[:5]
                            x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
                        else:
                            continue

                        rect = (x0, y0, x1, y1)
                        # filtre : ne pas peindre les rectangles internes aux grilles détectées
                        if self._rect_inside_any(rect, grid_bboxes):
                            continue

                        html.append(
                            f'<div style="position:absolute;left:{x0}px;top:{y0}px;'
                            f'width:{x1 - x0}px;height:{y1 - y0}px;border:1px solid #333;'
                            f'z-index:0;pointer-events:none;"></div>'
                        )

                    # autres commandes ignorées
                except Exception as e_item:
                    print(f"      Skip drawing item {it[:2]}… cause: {e_item}")
                    continue

        return "".join(html)

    def _collect_vector_primitives(self, page):
        """Retourne listes de segments horizontaux/verticaux et rectangles (bbox)."""
        H, V, RECTS = [], [], []
        try:
            for d in page.get_drawings():
                for it in d.get("items", []):
                    cmd = it[0] if it else None
                    if cmd == "l":
                        # ('l', (x0,y0),(x1,y1), ...) ou ('l', x0,y0,x1,y1,...)
                        if len(it) >= 3 and isinstance(it[1], (tuple, list)):
                            x0, y0 = float(it[1][0]), float(it[1][1])
                            x1, y1 = float(it[2][0]), float(it[2][1])
                        elif len(it) >= 5:
                            _, x0, y0, x1, y1 = it[:5]
                            x0, y0, x1, y1 = float(x0), float(y0), float(x1), float(y1)
                        else:
                            continue
                        if abs(y1 - y0) < 0.5:  # horizontale
                            H.append((min(x0, x1), y0, max(x0, x1), y0))
                        elif abs(x1 - x0) < 0.5:  # verticale
                            V.append((x0, min(y0, y1), x0, max(y0, y1)))
                    elif cmd == "re":
                        # ('re', fitz.Rect) ou ('re', x0,y0,x1,y1,...)
                        if len(it) >= 2 and hasattr(it[1], "x0"):
                            r = it[1]
                            RECTS.append((float(r.x0), float(r.y0), float(r.x1), float(r.y1)))
                        elif len(it) >= 5:
                            _, x0, y0, x1, y1 = it[:5]
                            RECTS.append((float(x0), float(y0), float(x1), float(y1)))
        except Exception as e:
            print(f"    _collect_vector_primitives error: {e}")
        return H, V, RECTS

    def _zone_has_vector_grid(self, bbox, H, V, RECTS):
        """
        True si la zone bbox contient une grille déjà tracée dans le PDF :
        - au moins 3 horizontales + 3 verticales qui tombent dans la zone, ou
        - un grand rectangle englobant.
        """
        x0, y0, x1, y1 = bbox

        def inside_line_h(h):  # h=(lx0, ly, lx1, ly)
            return (y0 - 1 <= h[1] <= y1 + 1) and (max(0, min(h[2], x1) - max(h[0], x0)) > 5)

        def inside_line_v(v):  # v=(lx, ly0, lx, ly1)
            return (x0 - 1 <= v[0] <= x1 + 1) and (max(0, min(v[3], y1) - max(v[1], y0)) > 5)

        def inside_rect(r):
            rx0, ry0, rx1, ry1 = r
            w_cov = max(0, min(rx1, x1) - max(rx0, x0)) / max(1, (x1 - x0))
            h_cov = max(0, min(ry1, y1) - max(ry0, y0)) / max(1, (y1 - y0))
            return w_cov > 0.6 and h_cov > 0.4

        h_in = [h for h in H if inside_line_h(h)]
        v_in = [v for v in V if inside_line_v(v)]
        if any(inside_rect(r) for r in RECTS):
            return True
        return (len(h_in) >= 3 and len(v_in) >= 3)

    def _fallback_simple_extraction(self, page, page_num):
        """Extraction simple en cas d'échec"""
        content = page.get_text() or ""
        page_html = f'''
        <div class="pdf-page-simple" style="
            width: 595px; height: 842px; margin: 20px auto;
            background: white; border: 1px solid #ddd; padding: 20px;
            font-family: 'Times New Roman', Times, serif; line-height: 1.4;
        ">
            <pre style="white-space: pre-wrap; font-family: inherit;">{self._escape_html(content)}</pre>
        </div>
        '''
        return content, page_html, [], set()

    def _extract_image_data(self, page, img, page_num, img_index):
        """Extrait les données d'une image"""
        try:
            xref = img[0]
            base_image = page.parent.extract_image(xref)

            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_base64 = base64.b64encode(image_bytes).decode()

            return {
                'data': image_bytes,
                'base64': image_base64,
                'format': image_ext,
                'name': f'page_{page_num + 1}_img_{img_index + 1}.{image_ext}'
            }

        except Exception as e:
            print(f"        Erreur extraction données image: {e}")
            return None

    def _generate_improved_css(self):
        """CSS avec styles pour notes de bas de page"""
        css_base = """
        .pdf-document-exact {
            background: #f0f0f0;
            padding: 20px;
            font-family: 'Times New Roman', Times, serif;
        }

        .pdf-page-exact {
            position: relative !important;
            background: white !important;
            margin: 20px auto !important;
            border: 1px solid #ccc !important;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1) !important;
            transform-origin: top center;
            transition: transform 0.3s ease;
            overflow: visible !important;
        }

        .pdf-table-smart {
            border-collapse: collapse !important;
            font-family: 'Times New Roman', Times, serif !important;
            background: white !important;
            margin: 0 !important;
            font-size: 9px !important;
            line-height: 1.2 !important;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .pdf-table-smart th,
        .pdf-table-smart td {
            border: 1px solid #333 !important;
            padding: 4px 6px !important;
            vertical-align: top !important;
            word-wrap: break-word;
            max-width: 120px;
        }

        .pdf-table-smart th {
            background-color: #f0f0f0 !important;
            font-weight: bold !important;
            text-align: center !important;
            border-bottom: 2px solid #333 !important;
            font-size: 9px !important;
        }

        .pdf-text-element {
            position: absolute !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            background: transparent !important;
            transform: none !important;
            font-family: 'Times New Roman', Times, serif !important;
            z-index: 2 !important;
            user-select: text !important;
        }

        .pdf-footnote {
            position: absolute !important;
            margin: 0 !important;
            padding: 2px !important;
            border: none !important;
            background: transparent !important;
            font-family: 'Times New Roman', Times, serif !important;
            font-size: 7px !important;
            color: #666 !important;
            line-height: 1.2 !important;
            max-width: 400px;
            z-index: 2 !important;
            user-select: text !important;
        }

        .pdf-image-exact {
            position: absolute !important;
            margin: 0 !important;
            padding: 0 !important;
            border: none !important;
            transform: none !important;
            z-index: 0 !important;
            pointer-events: none !important;
        }
        """
        return css_base

    def _convert_color(self, color_value):
        """Convertit une couleur PDF en CSS"""
        if isinstance(color_value, (int, float)):
            if color_value == 0:
                return "#000000"
            elif color_value == 1:
                return "#ffffff"
            else:
                gray = int(color_value * 255)
                return f"#{gray:02x}{gray:02x}{gray:02x}"
        elif isinstance(color_value, (list, tuple)) and len(color_value) >= 3:
            r = int(max(0, min(255, color_value[0] * 255)))
            g = int(max(0, min(255, color_value[1] * 255)))
            b = int(max(0, min(255, color_value[2] * 255)))
            return f"#{r:02x}{g:02x}{b:02x}"
        return "#000000"

    def _normalize_font(self, font_name):
        """Normalise les noms de police PDF vers des polices web"""
        font_map = {
            'Times-Roman': 'Times New Roman',
            'Times-Bold': 'Times New Roman',
            'Times-Italic': 'Times New Roman',
            'Times-BoldItalic': 'Times New Roman',
            'Helvetica': 'Arial',
            'Helvetica-Bold': 'Arial',
            'Helvetica-Oblique': 'Arial',
            'Helvetica-BoldOblique': 'Arial',
            'Courier': 'Courier New',
            'Courier-Bold': 'Courier New',
            'Courier-Oblique': 'Courier New',
            'Courier-BoldOblique': 'Courier New'
        }

        clean_name = font_name.split('+')[-1] if '+' in font_name else font_name
        return font_map.get(clean_name, clean_name)

    def _escape_html(self, text):
        """Échappe le texte pour HTML"""
        if not text:
            return ""
        return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&#39;'))

    def _detect_tables_in_content(self, content):
        """Détection simple de tableaux dans le contenu"""
        lines = content.split('\n')
        table_indicators = 0

        for line in lines:
            if len(line.split()) > 3 and ('.' in line or '|' in line or '\t' in line):
                table_indicators += 1

        return table_indicators > 2

    def _parse_pdf_date(self, pdf_date):
        """Parse une date PDF"""
        if not pdf_date:
            return None

        try:
            if pdf_date.startswith("D:"):
                pdf_date = pdf_date[2:]

            date_part = pdf_date[:14]

            if len(date_part) >= 8:
                if len(date_part) >= 14:
                    dt = datetime.strptime(date_part[:14], "%Y%m%d%H%M%S")
                else:
                    dt = datetime.strptime(date_part[:8], "%Y%m%d")
                return timezone.make_aware(dt)
        except:
            pass

        return None

    # Méthodes fallback
    def _process_with_pdfplumber_simple(self, file_path):
        """Fallback simple avec pdfplumber"""
        try:
            content = ""
            formatted_content = ""

            with pdfplumber.open(file_path) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    page_text = page.extract_text() or ""
                    content += f"\n--- Page {page_num + 1} ---\n{page_text}\n"

                    page_html = f'''
                    <div class="pdf-page-simple" style="
                        width: 800px; height: 1000px; position: relative; margin: 20px auto;
                        background: white; border: 1px solid #ddd; padding: 20px;">
                        <pre style="font-family: inherit; font-size: 12px; white-space: pre-wrap;">{self._escape_html(page_text)}</pre>
                    </div>
                    '''
                    formatted_content += page_html

            return {
                'content': content,
                'formatted_content': f'<div class="pdf-document-exact">{formatted_content}</div>',
                'author': '',
                'creation_date': None,
                'modification_date': None,
                'images': [],
                'format_info': {
                    'page_width': 800,
                    'page_height': 1000,
                    'fonts_used': [],
                    'has_images': False,
                    'has_tables': self._detect_tables_in_content(content),
                    'has_headers': False,
                    'has_footers': False,
                    'generated_css': self._generate_improved_css()
                }
            }

        except Exception as e:
            return self._process_basic_fallback_with_message(f"Erreur pdfplumber: {str(e)}")

    def _process_basic_fallback(self, file_path):
        """Fallback de base"""
        return self._process_basic_fallback_with_message("Aucune bibliothèque PDF disponible")

    def _process_basic_fallback_with_message(self, error_msg):
        """Fallback avec message d'erreur"""
        return {
            'content': f"Impossible d'extraire le contenu PDF: {error_msg}",
            'formatted_content': f'''
            <div class="pdf-document-exact">
                <div class="pdf-page-exact" style="width: 595px; height: 842px; margin: 20px auto; background: white; border: 1px solid #ddd; padding: 40px; text-align: center;">
                    <h3>📄 Document PDF</h3>
                    <p><strong>Problème:</strong> {error_msg}</p>
                    <p>Installez PyMuPDF pour une extraction fidèle :</p>
                    <code>pip install PyMuPDF</code>
                </div>
            </div>
            ''',
            'author': '',
            'creation_date': None,
            'modification_date': None,
            'images': [],
            'format_info': {
                'page_width': 595,
                'page_height': 842,
                'fonts_used': [],
                'has_images': False,
                'has_tables': False,
                'has_headers': False,
                'has_footers': False,
                'generated_css': self._generate_improved_css()
            }
        }
