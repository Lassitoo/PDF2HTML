from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
import os
from .models import Document

# Importer magic seulement si disponible
try:
    import magic

    MAGIC_AVAILABLE = True
except ImportError:
    MAGIC_AVAILABLE = False


class DocumentUploadForm(forms.ModelForm):
    """Formulaire pour l'upload de documents"""

    class Meta:
        model = Document
        fields = ['title', 'description', 'original_file']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Titre du document (optionnel)'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Description du document (optionnel)'
            }),
            'original_file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.docx,.doc,.txt,.html,.xlsx,.xls,.rtf'
            })
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.fields['original_file'].required = True

    def clean_original_file(self):
        """Valide le fichier uploadé"""
        file = self.cleaned_data.get('original_file')

        if file:
            # Vérifier la taille
            if file.size > settings.MAX_UPLOAD_SIZE:
                raise ValidationError(
                    f'Le fichier est trop volumineux. Taille maximum: {settings.MAX_UPLOAD_SIZE // (1024 * 1024)} MB'
                )

            # Vérifier le type de fichier
            file_type = self._get_file_type(file)

            if file_type not in settings.ALLOWED_DOCUMENT_TYPES:
                allowed_extensions = ['.pdf', '.docx', '.doc', '.txt', '.html', '.xlsx', '.xls', '.rtf']
                raise ValidationError(
                    f'Type de fichier non supporté. Types autorisés: {", ".join(allowed_extensions)}'
                )

        return file

    def clean_title(self):
        """Génère un titre automatique si non fourni"""
        title = self.cleaned_data.get('title')
        original_file = self.cleaned_data.get('original_file')

        if not title and original_file:
            # Générer un titre basé sur le nom du fichier
            filename = original_file.name
            title = os.path.splitext(filename)[0]

            # Nettoyer le titre
            title = title.replace('_', ' ').replace('-', ' ').title()

        return title or 'Document sans titre'

    def _get_file_type(self, file):
        """Détermine le type MIME du fichier"""
        if MAGIC_AVAILABLE:
            try:
                # Lire les premiers bytes pour détection
                file.seek(0)
                file_content = file.read(2048)
                file.seek(0)

                mime = magic.Magic(mime=True)
                return mime.from_buffer(file_content)

            except Exception as e:
                # Fallback sur l'extension si magic échoue
                pass

        # Fallback sur l'extension (sans magic)
        ext = os.path.splitext(file.name)[1].lower()
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

    def save(self, commit=True):
        """Sauvegarde le document avec les métadonnées"""
        document = super().save(commit=False)

        if self.user:
            document.uploaded_by = self.user

        # Déterminer le type de fichier et la taille
        if document.original_file:
            document.file_size = document.original_file.size

            # Déterminer l'extension pour le type
            ext = os.path.splitext(document.original_file.name)[1].lower()
            type_map = {
                '.pdf': 'pdf',
                '.docx': 'docx',
                '.doc': 'doc',
                '.txt': 'txt',
                '.html': 'html',
                '.xlsx': 'xlsx',
                '.xls': 'xls',
                '.rtf': 'rtf'
            }
            document.file_type = type_map.get(ext, 'unknown')

        if commit:
            document.save()

        return document


class DocumentFilterForm(forms.Form):
    """Formulaire pour filtrer les documents"""

    SORT_CHOICES = [
        ('-uploaded_at', 'Plus récent d\'abord'),
        ('uploaded_at', 'Plus ancien d\'abord'),
        ('title', 'Titre (A-Z)'),
        ('-title', 'Titre (Z-A)'),
        ('file_size', 'Taille (petit à grand)'),
        ('-file_size', 'Taille (grand à petit)'),
    ]

    STATUS_CHOICES = [
        ('', 'Tous les statuts'),
        ('pending', 'En attente'),
        ('processing', 'En cours'),
        ('completed', 'Traités'),
        ('error', 'Erreurs'),
    ]

    TYPE_CHOICES = [
        ('', 'Tous les types'),
        ('pdf', 'PDF'),
        ('docx', 'Word'),
        ('doc', 'Word (ancien)'),
        ('txt', 'Texte'),
        ('html', 'HTML'),
        ('xlsx', 'Excel'),
        ('xls', 'Excel (ancien)'),
        ('rtf', 'RTF'),
    ]

    search = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Rechercher dans les titres...'
        })
    )

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    file_type = forms.ChoiceField(
        choices=TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    sort_by = forms.ChoiceField(
        choices=SORT_CHOICES,
        required=False,
        initial='-uploaded_at',
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )