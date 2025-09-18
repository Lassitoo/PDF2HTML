import os
import io
from PIL import Image
from django.core.files.base import ContentFile
from django.conf import settings


class ImageProcessor:
    """Processeur pour les images extraites des documents"""

    def __init__(self):
        self.max_width = 1200
        self.max_height = 1200
        self.quality = 85

    def save_image(self, image_data, filename):
        """Sauvegarde une image avec optimisation"""
        try:
            # Ouvrir l'image avec PIL
            image = Image.open(io.BytesIO(image_data))

            # Optimiser l'image
            optimized_image = self._optimize_image(image)

            # Convertir en bytes
            output_buffer = io.BytesIO()

            # Déterminer le format de sortie
            output_format = 'PNG' if optimized_image.mode == 'RGBA' else 'JPEG'

            if output_format == 'JPEG':
                # Convertir RGBA en RGB pour JPEG
                if optimized_image.mode == 'RGBA':
                    background = Image.new('RGB', optimized_image.size, (255, 255, 255))
                    background.paste(optimized_image, mask=optimized_image.split()[-1])
                    optimized_image = background

                optimized_image.save(output_buffer, format='JPEG', quality=self.quality, optimize=True)
                filename = filename.replace('.png', '.jpg')
            else:
                optimized_image.save(output_buffer, format='PNG', optimize=True)

            # Créer un fichier Django
            django_file = ContentFile(output_buffer.getvalue())
            django_file.name = filename

            return django_file

        except Exception as e:
            # En cas d'erreur, sauvegarder l'image originale
            django_file = ContentFile(image_data)
            django_file.name = filename
            return django_file

    def _optimize_image(self, image):
        """Optimise une image (redimensionnement et compression)"""
        # Copier l'image pour éviter de modifier l'original
        optimized = image.copy()

        # Redimensionner si nécessaire
        if optimized.width > self.max_width or optimized.height > self.max_height:
            optimized.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)

        return optimized

    def extract_images_from_html(self, html_content):
        """Extrait les images intégrées (base64) d'un contenu HTML"""
        from bs4 import BeautifulSoup
        import base64
        import re

        soup = BeautifulSoup(html_content, 'html.parser')
        images = []

        # Trouver toutes les images avec des données base64
        img_tags = soup.find_all('img')

        for i, img in enumerate(img_tags):
            src = img.get('src', '')

            if src.startswith('data:image/'):
                try:
                    # Extraire les données base64
                    header, data = src.split(',', 1)
                    image_data = base64.b64decode(data)

                    # Déterminer l'extension
                    if 'png' in header:
                        ext = 'png'
                    elif 'jpeg' in header or 'jpg' in header:
                        ext = 'jpg'
                    else:
                        ext = 'png'

                    images.append({
                        'data': image_data,
                        'name': f'embedded_image_{i}.{ext}',
                        'width': img.get('width'),
                        'height': img.get('height')
                    })

                except Exception as e:
                    continue

        return images

    def create_thumbnail(self, image_path, size=(200, 200)):
        """Crée une miniature d'une image"""
        try:
            with Image.open(image_path) as img:
                img.thumbnail(size, Image.Resampling.LANCZOS)

                # Sauvegarder la miniature
                thumb_buffer = io.BytesIO()
                img_format = 'PNG' if img.mode == 'RGBA' else 'JPEG'

                if img_format == 'JPEG' and img.mode == 'RGBA':
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    background.paste(img, mask=img.split()[-1])
                    img = background

                img.save(thumb_buffer, format=img_format, quality=self.quality)

                return thumb_buffer.getvalue()

        except Exception as e:
            return None

    def get_image_info(self, image_data):
        """Obtient les informations d'une image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                return {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': len(image_data)
                }
        except Exception as e:
            return None

    def convert_to_web_format(self, image_data):
        """Convertit une image vers un format web optimisé"""
        try:
            image = Image.open(io.BytesIO(image_data))

            # Optimiser pour le web
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')

            # Redimensionner si trop grande
            max_size = (800, 800)
            if image.width > max_size[0] or image.height > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Sauvegarder en JPEG optimisé
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='JPEG', quality=80, optimize=True)

            return output_buffer.getvalue()

        except Exception as e:
            return image_data  # Retourner l'original en cas d'erreur