import os
import io
from PIL import Image
from django.core.files.base import ContentFile
from django.conf import settings


class ImageProcessor:
    """Processeur pour les images extraites des documents avec amélioration de qualité"""

    def __init__(self):
        self.max_width = 2400  # Augmenté pour meilleure qualité
        self.max_height = 2400  # Augmenté pour meilleure qualité
        self.quality = 92  # Qualité augmentée pour préserver les détails

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
        """Optimise une image (redimensionnement et amélioration de qualité)"""
        # Copier l'image pour éviter de modifier l'original
        optimized = image.copy()

        # Améliorer la qualité pour les petites images (upscaling si nécessaire)
        min_size = 300  # Taille minimale recommandée
        if optimized.width < min_size and optimized.height < min_size:
            # Upscale les petites images pour meilleure visibilité
            scale_factor = min_size / min(optimized.width, optimized.height)
            new_width = int(optimized.width * scale_factor)
            new_height = int(optimized.height * scale_factor)
            optimized = optimized.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Redimensionner si nécessaire (seulement si vraiment trop grande)
        if optimized.width > self.max_width or optimized.height > self.max_height:
            optimized.thumbnail((self.max_width, self.max_height), Image.Resampling.LANCZOS)
        
        # Améliorer la netteté
        try:
            from PIL import ImageEnhance
            enhancer = ImageEnhance.Sharpness(optimized)
            optimized = enhancer.enhance(1.2)  # Légère amélioration de la netteté
        except:
            pass

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
                    print(f"Erreur extraction image base64: {e}")
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
        """Obtient les informations détaillées d'une image"""
        try:
            with Image.open(io.BytesIO(image_data)) as img:
                info = {
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'size_bytes': len(image_data),
                    'dpi': img.info.get('dpi', (72, 72)),
                    'is_small': img.width < 300 or img.height < 300,
                    'aspect_ratio': img.width / img.height if img.height > 0 else 1
                }
                return info
        except Exception as e:
            return None
    
    def enhance_image_quality(self, image_data, options=None):
        """Améliore la qualité d'une image avec options personnalisables"""
        if options is None:
            options = {
                'upscale': True,
                'denoise': False,
                'sharpen': True,
                'contrast_enhancement': True
            }
        
        try:
            image = Image.open(io.BytesIO(image_data))
            
            # Upscale si l'image est petite
            if options.get('upscale', True) and (image.width < 500 or image.height < 500):
                scale_factor = 2.0
                new_size = (int(image.width * scale_factor), int(image.height * scale_factor))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # Amélioration avec PIL ImageEnhance
            try:
                from PIL import ImageEnhance, ImageFilter
                
                # Débruitage (si demandé)
                if options.get('denoise', False):
                    image = image.filter(ImageFilter.MedianFilter(size=3))
                
                # Amélioration du contraste
                if options.get('contrast_enhancement', True):
                    enhancer = ImageEnhance.Contrast(image)
                    image = enhancer.enhance(1.2)
                
                # Amélioration de la netteté
                if options.get('sharpen', True):
                    enhancer = ImageEnhance.Sharpness(image)
                    image = enhancer.enhance(1.5)
                    
            except Exception as e:
                print(f"Erreur lors de l'amélioration: {e}")
            
            # Convertir en bytes
            output_buffer = io.BytesIO()
            if image.mode == 'RGBA':
                image.save(output_buffer, format='PNG', optimize=True)
            else:
                if image.mode != 'RGB':
                    image = image.convert('RGB')
                image.save(output_buffer, format='JPEG', quality=95, optimize=True)
            
            return output_buffer.getvalue()
            
        except Exception as e:
            print(f"Erreur enhancement: {e}")
            return image_data

    def convert_to_web_format(self, image_data):
        """Convertit une image vers un format web optimisé avec amélioration de qualité"""
        try:
            image = Image.open(io.BytesIO(image_data))

            # Optimiser pour le web
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGB')

            # Redimensionner si trop grande (seuil augmenté)
            max_size = (1600, 1600)  # Augmenté pour meilleure qualité
            if image.width > max_size[0] or image.height > max_size[1]:
                image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Améliorer le contraste et la netteté pour mieux voir les détails
            try:
                from PIL import ImageEnhance
                
                # Légère amélioration du contraste
                contrast = ImageEnhance.Contrast(image)
                image = contrast.enhance(1.1)
                
                # Légère amélioration de la netteté
                sharpness = ImageEnhance.Sharpness(image)
                image = sharpness.enhance(1.3)
            except:
                pass

            # Sauvegarder en JPEG optimisé avec qualité plus élevée
            output_buffer = io.BytesIO()
            image.save(output_buffer, format='JPEG', quality=90, optimize=True)

            return output_buffer.getvalue()

        except Exception as e:
            return image_data  # Retourner l'original en cas d'erreur
