import os
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Document(models.Model):
    DOCUMENT_TYPES = [
        ('pdf', 'PDF'),
        ('docx', 'Word Document'),
        ('doc', 'Word Document (Legacy)'),
        ('txt', 'Text File'),
        ('html', 'HTML File'),
        ('xlsx', 'Excel Spreadsheet'),
        ('xls', 'Excel Spreadsheet (Legacy)'),
        ('rtf', 'Rich Text Format'),
    ]

    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('processing', 'En cours de traitement'),
        ('completed', 'Traité'),
        ('error', 'Erreur'),
    ]

    # Informations de base
    title = models.CharField(max_length=255, verbose_name="Titre")
    description = models.TextField(blank=True, null=True, verbose_name="Description")

    # Fichier original
    original_file = models.FileField(upload_to='uploads/%Y/%m/', verbose_name="Fichier original")
    file_type = models.CharField(max_length=10, choices=DOCUMENT_TYPES, verbose_name="Type de fichier")
    file_size = models.BigIntegerField(verbose_name="Taille du fichier")

    # Contenu extrait
    extracted_content = models.TextField(blank=True, null=True, verbose_name="Contenu extrait")
    formatted_content = models.TextField(blank=True, null=True, verbose_name="Contenu formaté")

    # Métadonnées
    author = models.CharField(max_length=255, blank=True, null=True, verbose_name="Auteur")
    creation_date = models.DateTimeField(blank=True, null=True, verbose_name="Date de création du document")
    modification_date = models.DateTimeField(blank=True, null=True, verbose_name="Date de modification du document")

    # Statut et traçabilité
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending', verbose_name="Statut")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Téléchargé par")
    uploaded_at = models.DateTimeField(default=timezone.now, verbose_name="Téléchargé le")
    processed_at = models.DateTimeField(blank=True, null=True, verbose_name="Traité le")

    # Informations sur les erreurs
    error_message = models.TextField(blank=True, null=True, verbose_name="Message d'erreur")

    class Meta:
        verbose_name = "Document"
        verbose_name_plural = "Documents"
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title or self.original_file.name

    def get_file_extension(self):
        return os.path.splitext(self.original_file.name)[1].lower()

    def is_processed(self):
        return self.status == 'completed'

    def has_images(self):
        return self.images.exists()


class DocumentImage(models.Model):
    """Modèle pour stocker les images extraites des documents"""
    document = models.ForeignKey(Document, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='images/%Y/%m/', verbose_name="Image")
    image_name = models.CharField(max_length=255, verbose_name="Nom de l'image")
    position_in_document = models.IntegerField(verbose_name="Position dans le document")
    width = models.IntegerField(blank=True, null=True, verbose_name="Largeur")
    height = models.IntegerField(blank=True, null=True, verbose_name="Hauteur")

    class Meta:
        verbose_name = "Image du document"
        verbose_name_plural = "Images des documents"
        ordering = ['position_in_document']

    def __str__(self):
        return f"{self.document.title} - Image {self.position_in_document}"


class DocumentFormat(models.Model):
    """Modèle pour stocker les informations de formatage"""
    document = models.OneToOneField(Document, related_name='format_info', on_delete=models.CASCADE)

    # Informations de mise en page
    page_width = models.FloatField(blank=True, null=True, verbose_name="Largeur de page")
    page_height = models.FloatField(blank=True, null=True, verbose_name="Hauteur de page")
    margins = models.JSONField(blank=True, null=True, verbose_name="Marges")

    # Styles de police
    fonts_used = models.JSONField(blank=True, null=True, verbose_name="Polices utilisées")

    # Structure du document
    has_headers = models.BooleanField(default=False, verbose_name="A des en-têtes")
    has_footers = models.BooleanField(default=False, verbose_name="A des pieds de page")
    has_tables = models.BooleanField(default=False, verbose_name="A des tableaux")
    has_images = models.BooleanField(default=False, verbose_name="A des images")

    # CSS généré pour reproduire le style
    generated_css = models.TextField(blank=True, null=True, verbose_name="CSS généré")

    class Meta:
        verbose_name = "Format du document"
        verbose_name_plural = "Formats des documents"

    def __str__(self):
        return f"Format - {self.document.title}"