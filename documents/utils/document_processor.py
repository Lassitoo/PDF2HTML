import os
from django.conf import settings
from django.utils import timezone
from .pdf_processor import PDFProcessor
from .word_processor import WordProcessor
from .image_processor import ImageProcessor

# Importer magic seulement si disponible
try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


class DocumentProcessor:
    """Processeur principal pour tous types de documents"""

    def __init__(self, document_instance):
        self.document = document_instance
        self.pdf_processor = PDFProcessor()
        self.word_processor = WordProcessor()
        self.image_processor = ImageProcessor()
        self.extraction_metrics = {
            'total_elements_detected': 0,
            'total_elements_extracted': 0,
            'text_quality': 0,
            'image_quality': 0,
            'table_quality': 0,
            'errors': []
        }

    def detect_file_type(self, file_path):
        """Détecte le type MIME du fichier"""
        if MAGIC_AVAILABLE:
            try:
                mime = magic.Magic(mime=True)
                return mime.from_file(file_path)
            except:
                pass

        # Fallback sur l'extension si magic n'est pas disponible
        ext = os.path.splitext(file_path)[1].lower()
        mime_map = {
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.doc': 'application/msword',
            '.txt': 'text/plain',
            '.html': 'text/html',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.xls': 'application/vnd.ms-excel',
            '.rtf': 'application/rtf'
        }
        return mime_map.get(ext, 'application/octet-stream')

    def log_extraction_error(self, error_type, severity, message, details=None, page_number=None, element_type=None, suggested_fix=None):
        """Enregistre une erreur d'extraction"""
        # Si aucune page n'est spécifiée, essayer de déterminer la page actuelle
        if page_number is None:
            page_number = getattr(self, 'current_page_number', 1)

        # Générer automatiquement des corrections si aucune n'est fournie
        if suggested_fix is None:
            auto_corrections = self.apply_automatic_corrections(error_type, details)
            suggested_fix = "; ".join(auto_corrections[:2])  # Prendre les 2 premières suggestions

        error_data = {
            'error_type': error_type,
            'severity': severity,
            'message': message,
            'details': details,
            'page_number': page_number,
            'element_type': element_type,
            'suggested_fix': suggested_fix
        }
        self.extraction_metrics['errors'].append(error_data)

    def calculate_text_quality(self, extracted_text, expected_length=None):
        """Calcule la qualité d'extraction du texte"""
        if not extracted_text:
            return 0

        quality_score = 100

        # Détecter les caractères mal encodés ou corrompus
        corrupted_chars = len([c for c in extracted_text if ord(c) > 65535 or c in '��□?'])
        if corrupted_chars > 0:
            corruption_penalty = min(50, (corrupted_chars / len(extracted_text)) * 100)
            quality_score -= corruption_penalty
            if corruption_penalty > 10:
                self.log_extraction_error(
                    'encoding', 'medium',
                    f"Détection de {corrupted_chars} caractères corrompus",
                    {'corrupted_chars': corrupted_chars, 'total_chars': len(extracted_text)},
                    suggested_fix="Vérifier l'encodage du document source"
                )

        # Vérifier la structure du texte
        lines = extracted_text.split('\n')
        empty_lines = len([line for line in lines if not line.strip()])
        if empty_lines / len(lines) > 0.5:
            quality_score -= 20
            self.log_extraction_error(
                'layout_analysis', 'low',
                "Beaucoup de lignes vides détectées",
                {'empty_lines_ratio': empty_lines / len(lines)},
                suggested_fix="Le document pourrait nécessiter un OCR plus précis"
            )

        # Vérifier la longueur par rapport à l'attendu
        if expected_length and abs(len(extracted_text) - expected_length) / expected_length > 0.3:
            quality_score -= 15
            self.log_extraction_error(
                'text_ocr', 'medium',
                "Différence significative avec la longueur attendue",
                {'extracted_length': len(extracted_text), 'expected_length': expected_length}
            )

        return max(0, quality_score)

    def calculate_image_quality(self, images_data, total_images_detected=None):
        """Calcule la qualité d'extraction des images"""
        if not images_data:
            if total_images_detected and total_images_detected > 0:
                self.log_extraction_error(
                    'image_extraction', 'high',
                    f"Aucune image extraite alors que {total_images_detected} ont été détectées",
                    {'detected': total_images_detected, 'extracted': 0}
                )
                return 0
            return 100

        successful_extractions = 0
        for i, img_data in enumerate(images_data):
            try:
                if img_data.get('data') and len(img_data['data']) > 0:
                    successful_extractions += 1
                    # Vérifier la qualité de l'image
                    if img_data.get('width', 0) < 50 or img_data.get('height', 0) < 50:
                        self.log_extraction_error(
                            'image_extraction', 'low',
                            f"Image {i+1} de très petite taille",
                            {'width': img_data.get('width'), 'height': img_data.get('height')},
                            suggested_fix="L'image pourrait être de mauvaise qualité ou corrompue"
                        )
                else:
                    self.log_extraction_error(
                        'image_extraction', 'medium',
                        f"Échec d'extraction de l'image {i+1}",
                        {'image_index': i}
                    )
            except Exception as e:
                self.log_extraction_error(
                    'image_extraction', 'high',
                    f"Erreur lors du traitement de l'image {i+1}: {str(e)}",
                    {'image_index': i, 'error': str(e)}
                )

        if len(images_data) > 0:
            return (successful_extractions / len(images_data)) * 100
        return 100

    def calculate_table_quality(self, content, format_info):
        """Calcule la qualité d'extraction des tableaux"""
        has_tables = format_info.get('has_tables', False)

        if not has_tables:
            return 100  # Pas de tableaux à extraire

        # Rechercher des indicateurs de tableaux dans le contenu
        table_indicators = content.count('<table>') + content.count('|') + content.count('\t')

        if table_indicators == 0:
            self.log_extraction_error(
                'table_parsing', 'high',
                "Tableaux détectés mais non extraits correctement",
                suggested_fix="Le document contient des tableaux complexes nécessitant un traitement spécialisé"
            )
            return 20

        # Vérifier la structure des tableaux
        if '<table>' in content:
            table_count = content.count('<table>')
            complete_tables = content.count('</table>')
            if table_count != complete_tables:
                self.log_extraction_error(
                    'table_parsing', 'medium',
                    "Tableaux HTML incomplets détectés",
                    {'incomplete_tables': table_count - complete_tables}
                )
                return 60

        return 85  # Score par défaut pour les tableaux détectés

    def update_extraction_metrics(self, result):
        """Met à jour les métriques d'extraction"""
        content = result.get('content', '')
        formatted_content = result.get('formatted_content', '')
        images = result.get('images', [])
        format_info = result.get('format_info', {})

        # Analyser les pages pour déterminer le nombre total
        self.current_page_count = self._estimate_page_count(content, formatted_content)

        # Compter les éléments détectés et extraits
        self.extraction_metrics['total_elements_detected'] += 1  # Le document lui-même
        self.extraction_metrics['total_elements_extracted'] += 1 if content else 0

        # Images
        total_images_detected = len(images) if images else 0
        if format_info.get('has_images'):
            total_images_detected = max(total_images_detected, 1)

        self.extraction_metrics['total_elements_detected'] += total_images_detected
        self.extraction_metrics['total_elements_extracted'] += len([img for img in images if img.get('data')])

        # Tableaux
        if format_info.get('has_tables'):
            self.extraction_metrics['total_elements_detected'] += 1
            # Compter comme extrait si on trouve des indicateurs de tableau
            if any(indicator in formatted_content for indicator in ['<table>', '|', '\t']):
                self.extraction_metrics['total_elements_extracted'] += 1

        # Calculer les qualités
        self.extraction_metrics['text_quality'] = self.calculate_text_quality(content)
        self.extraction_metrics['image_quality'] = self.calculate_image_quality(images, total_images_detected)
        self.extraction_metrics['table_quality'] = self.calculate_table_quality(formatted_content, format_info)

    def _estimate_page_count(self, content, formatted_content):
        """Estime le nombre de pages basé sur le contenu"""
        if 'pdf-page' in formatted_content:
            # Compter les divs de page PDF
            return formatted_content.count('pdf-page')
        elif content:
            # Estimation basée sur la longueur du texte (environ 500 mots par page)
            word_count = len(content.split())
            return max(1, word_count // 500)
        return 1

    def apply_automatic_corrections(self, error_type, details=None):
        """Applique des corrections automatiques selon le type d'erreur"""
        corrections = []

        if error_type == 'encoding':
            corrections = [
                "Ré-encoder le document avec UTF-8",
                "Utiliser un OCR avec détection automatique d'encodage",
                "Convertir le document en PDF avant extraction"
            ]
        elif error_type == 'image_extraction':
            corrections = [
                "Augmenter la résolution DPI pour l'extraction",
                "Utiliser un algorithme d'amélioration d'image",
                "Convertir les images en format standard (PNG/JPEG)"
            ]
        elif error_type == 'table_parsing':
            corrections = [
                "Appliquer un pré-traitement de détection de bordures",
                "Utiliser un algorithme spécialisé pour tableaux complexes",
                "Convertir en format avec grille structurée"
            ]
        elif error_type == 'text_ocr':
            corrections = [
                "Appliquer un filtre de débruitage d'image",
                "Utiliser un modèle OCR plus avancé",
                "Améliorer la résolution du document source"
            ]
        elif error_type == 'layout_analysis':
            corrections = [
                "Appliquer une détection automatique de colonnes",
                "Utiliser un algorithme de segmentation de page",
                "Ré-analyser avec détection de zones de texte"
            ]
        elif error_type == 'font_detection':
            corrections = [
                "Normaliser les polices vers des équivalents standard",
                "Utiliser une bibliothèque de substitution de polices",
                "Convertir en format texte uniforme"
            ]
        else:
            corrections = [
                "Retraiter le document avec des paramètres optimisés",
                "Utiliser un processeur alternatif",
                "Vérifier l'intégrité du fichier source"
            ]

        return corrections

    def save_extraction_errors(self):
        """Sauvegarde les erreurs d'extraction en base"""
        try:
            from ..models import DocumentExtractionError

            for error_data in self.extraction_metrics['errors']:
                DocumentExtractionError.objects.create(
                    document=self.document,
                    **error_data
                )
        except Exception as e:
            print(f"Erreur lors de la sauvegarde des erreurs d'extraction: {e}")

    def save_extraction_metrics(self):
        """Sauvegarde les métriques de précision"""
        try:
            metrics = self.extraction_metrics

            # Calculer la précision globale
            if metrics['total_elements_detected'] > 0:
                precision = (metrics['total_elements_extracted'] / metrics['total_elements_detected']) * 100
            else:
                precision = 100

            # Sauvegarder dans le document
            self.document.extraction_precision = round(precision, 2)
            self.document.total_elements_detected = metrics['total_elements_detected']
            self.document.total_elements_extracted = metrics['total_elements_extracted']
            self.document.text_extraction_quality = round(metrics['text_quality'], 2)
            self.document.image_extraction_quality = round(metrics['image_quality'], 2)
            self.document.table_extraction_quality = round(metrics['table_quality'], 2)

            self.document.save()

            # Sauvegarder les erreurs
            self.save_extraction_errors()

        except Exception as e:
            print(f"Erreur lors de la sauvegarde des métriques: {e}")

    def process_document(self):
        """Traite le document selon son type"""
        try:
            print(f"Début du traitement du document: {self.document.title}")
            self.document.status = 'processing'
            self.document.save()

            file_path = self.document.original_file.path
            mime_type = self.detect_file_type(file_path)

            print(f"Type MIME détecté: {mime_type}")

            # Déterminer le processeur approprié
            result = None

            if mime_type == 'application/pdf':
                print("Traitement PDF...")
                result = self.pdf_processor.process(file_path, self.document)

            elif mime_type in ['application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                               'application/msword']:
                print("Traitement Word...")
                try:
                    result = self.word_processor.process(file_path, self.document)
                except Exception as e:
                    print(f"Erreur Word processor: {e}")
                    # Fallback vers traitement texte simple
                    result = self._process_text_file(file_path)

            elif mime_type == 'text/plain':
                print("Traitement texte...")
                result = self._process_text_file(file_path)

            elif mime_type == 'text/html':
                print("Traitement HTML...")
                result = self._process_html_file(file_path)

            else:
                print(f"Type non supporté: {mime_type}, fallback vers texte")
                result = self._process_text_file(file_path)

            if not result:
                raise ValueError("Aucun résultat du processeur")

            # Sauvegarder les résultats
            self.document.extracted_content = result.get('content', '')
            self.document.formatted_content = result.get('formatted_content', '')
            self.document.author = result.get('author', '')
            self.document.creation_date = result.get('creation_date')
            self.document.modification_date = result.get('modification_date')
            self.document.status = 'completed'
            self.document.processed_at = timezone.now()
            self.document.save()

            print(f"Document traité avec succès: {len(self.document.extracted_content)} caractères extraits")

            # Sauvegarder les informations de formatage
            format_info = result.get('format_info', {})
            if format_info:
                self._save_format_info(format_info)

            # Traiter les images
            images = result.get('images', [])
            if images:
                print(f"Traitement de {len(images)} images...")
                self._save_images(images)

            # Calculer et sauvegarder les métriques de précision
            self.update_extraction_metrics(result)
            self.save_extraction_metrics()

            print(f"Métriques de précision: {self.document.extraction_precision}%")
            print(f"Erreurs détectées: {len(self.extraction_metrics['errors'])}")

            return True

        except Exception as e:
            print(f"Erreur lors du traitement: {str(e)}")
            import traceback
            traceback.print_exc()
            self.document.status = 'error'
            self.document.error_message = f"Erreur lors du traitement: {str(e)}"
            self.document.save()
            return False

    def _save_format_info(self, format_info):
        """Sauvegarde les informations de formatage"""
        try:
            from ..models import DocumentFormat
            doc_format, created = DocumentFormat.objects.get_or_create(
                document=self.document,
                defaults=format_info
            )
            if not created:
                for key, value in format_info.items():
                    setattr(doc_format, key, value)
                doc_format.save()
        except Exception as e:
            print(f"Erreur sauvegarde format info: {e}")

    def _process_text_file(self, file_path):
        """Traite un fichier texte simple"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except:
            # Fallback avec d'autres encodages
            try:
                with open(file_path, 'r', encoding='latin-1', errors='ignore') as f:
                    content = f.read()
            except:
                with open(file_path, 'r', encoding='cp1252', errors='ignore') as f:
                    content = f.read()

        # Convertir en HTML avec formatage basique
        html_content = content.replace('\n', '<br>\n')
        html_content = f'<div class="text-document"><pre>{html_content}</pre></div>'

        return {
            'content': content,
            'formatted_content': html_content,
            'format_info': {
                'has_headers': False,
                'has_footers': False,
                'has_tables': False,
                'has_images': False,
                'generated_css': '.text-document { font-family: monospace; white-space: pre-wrap; }'
            }
        }

    def _process_html_file(self, file_path):
        """Traite un fichier HTML"""
        try:
            from bs4 import BeautifulSoup

            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'html.parser')

            # Extraire le texte
            content = soup.get_text()

            # Analyser la structure
            has_images = bool(soup.find_all('img'))
            has_tables = bool(soup.find_all('table'))

            # Extraire le CSS inline
            css_content = ""
            for style_tag in soup.find_all('style'):
                css_content += style_tag.get_text()

            return {
                'content': content,
                'formatted_content': html_content,
                'format_info': {
                    'has_headers': False,
                    'has_footers': False,
                    'has_tables': has_tables,
                    'has_images': has_images,
                    'generated_css': css_content
                }
            }
        except Exception as e:
            print(f"Erreur traitement HTML: {e}")
            return self._process_text_file(file_path)

    def _save_images(self, images):
        """Sauvegarde les images extraites"""
        try:
            from ..models import DocumentImage

            for i, image_data in enumerate(images):
                try:
                    # Sauvegarder l'image
                    image_file = self.image_processor.save_image(
                        image_data['data'],
                        f"{self.document.id}_image_{i}.png"
                    )

                    # Créer l'enregistrement
                    DocumentImage.objects.create(
                        document=self.document,
                        image=image_file,
                        image_name=image_data.get('name', f'Image {i + 1}'),
                        position_in_document=i,
                        width=image_data.get('width'),
                        height=image_data.get('height')
                    )
                except Exception as e:
                    print(f"Erreur sauvegarde image {i}: {e}")
                    continue
        except Exception as e:
            print(f"Erreur générale sauvegarde images: {e}")
