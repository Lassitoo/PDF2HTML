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