from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.db.models import Count
from .models import Document, DocumentImage, DocumentFormat


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = [
        'title',
        'file_type_icon',
        'status_badge',
        'uploaded_by',
        'file_size_formatted',
        'uploaded_at',
        'processed_at',
        'has_images_icon',
        'actions_column'
    ]

    list_filter = [
        'status',
        'file_type',
        'uploaded_at',
        'processed_at',
        'uploaded_by'
    ]

    search_fields = [
        'title',
        'description',
        'author',
        'extracted_content',
        'original_file'
    ]

    readonly_fields = [
        'file_size',
        'uploaded_at',
        'processed_at',
        'file_preview',
        'processing_info'
    ]

    fieldsets = (
        ('Informations générales', {
            'fields': (
                'title',
                'description',
                'original_file',
                'file_preview'
            )
        }),
        ('Métadonnées du fichier', {
            'fields': (
                'file_type',
                'file_size',
                'author',
                'creation_date',
                'modification_date'
            )
        }),
        ('Traitement', {
            'fields': (
                'status',
                'uploaded_by',
                'uploaded_at',
                'processed_at',
                'error_message',
                'processing_info'
            )
        }),
        ('Contenu extrait', {
            'fields': (
                'extracted_content',
                'formatted_content'
            ),
            'classes': ('collapse',)
        })
    )

    def file_type_icon(self, obj):
        """Affiche l'icône du type de fichier"""
        icons = {
            'pdf': ('bi-file-earmark-pdf', 'text-danger'),
            'docx': ('bi-file-earmark-word', 'text-primary'),
            'doc': ('bi-file-earmark-word', 'text-primary'),
            'xlsx': ('bi-file-earmark-excel', 'text-success'),
            'xls': ('bi-file-earmark-excel', 'text-success'),
            'txt': ('bi-file-earmark-text', 'text-info'),
            'html': ('bi-file-earmark-code', 'text-warning'),
            'rtf': ('bi-file-earmark-richtext', 'text-secondary')
        }
        icon, color = icons.get(obj.file_type, ('bi-file-earmark', 'text-muted'))
        return format_html(
            '<i class="bi {} {} fs-4" title="{}"></i>',
            icon,
            color,
            obj.get_file_type_display()
        )

    file_type_icon.short_description = 'Type'
    file_type_icon.admin_order_field = 'file_type'

    def status_badge(self, obj):
        """Affiche le statut avec un badge coloré"""
        colors = {
            'pending': 'secondary',
            'processing': 'warning',
            'completed': 'success',
            'error': 'danger'
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display()
        )

    status_badge.short_description = 'Statut'
    status_badge.admin_order_field = 'status'

    def file_size_formatted(self, obj):
        """Affiche la taille du fichier formatée"""
        if obj.file_size:
            if obj.file_size >= 1024 ** 3:  # GB
                size = obj.file_size / (1024 ** 3)
                unit = 'GB'
            elif obj.file_size >= 1024 ** 2:  # MB
                size = obj.file_size / (1024 ** 2)
                unit = 'MB'
            elif obj.file_size >= 1024:  # KB
                size = obj.file_size / 1024
                unit = 'KB'
            else:
                size = obj.file_size
                unit = 'B'

            return f"{size:.1f} {unit}"
        return '-'

    file_size_formatted.short_description = 'Taille'
    file_size_formatted.admin_order_field = 'file_size'

    def has_images_icon(self, obj):
        """Indique si le document contient des images"""
        if obj.images.exists():
            count = obj.images.count()
            return format_html(
                '<i class="bi bi-images text-success" title="{} image{}"></i> {}',
                count,
                's' if count > 1 else '',
                count
            )
        return format_html('<i class="bi bi-image text-muted" title="Aucune image"></i>')

    has_images_icon.short_description = 'Images'

    def actions_column(self, obj):
        """Colonne d'actions rapides"""
        actions = []

        # Lien vers les détails
        detail_url = reverse('admin:documents_document_change', args=[obj.pk])
        actions.append(
            format_html(
                '<a href="{}" class="btn btn-sm btn-outline-primary" title="Modifier">'
                '<i class="bi bi-pencil"></i></a>',
                detail_url
            )
        )

        # Téléchargement du fichier original si disponible
        if obj.original_file:
            actions.append(
                format_html(
                    '<a href="{}" class="btn btn-sm btn-outline-secondary" title="Télécharger" target="_blank">'
                    '<i class="bi bi-download"></i></a>',
                    obj.original_file.url
                )
            )

        # Export HTML si traité
        if obj.status == 'completed':
            export_url = reverse('documents:export_html', args=[obj.pk])
            actions.append(
                format_html(
                    '<a href="{}" class="btn btn-sm btn-outline-success" title="Exporter HTML" target="_blank">'
                    '<i class="bi bi-file-code"></i></a>',
                    export_url
                )
            )

        return format_html(' '.join(actions))

    actions_column.short_description = 'Actions'

    def file_preview(self, obj):
        """Affiche un aperçu du fichier"""
        if not obj.original_file:
            return "Aucun fichier"

        preview_html = f"""
        <div class="file-preview" style="max-width: 300px;">
            <div class="d-flex align-items-center mb-2">
                {self.file_type_icon(obj)}
                <div class="ms-2">
                    <strong>{obj.original_file.name}</strong><br>
                    <small class="text-muted">{self.file_size_formatted(obj)}</small>
                </div>
            </div>
        """

        if obj.original_file.url.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
            preview_html += f'''
                <img src="{obj.original_file.url}" 
                     style="max-width: 100%; max-height: 200px; border: 1px solid #ddd; border-radius: 4px;"
                     alt="Aperçu">
            '''

        preview_html += "</div>"
        return mark_safe(preview_html)

    file_preview.short_description = 'Aperçu'

    def processing_info(self, obj):
        """Affiche les informations de traitement"""
        info_html = "<div class='processing-info'>"

        # Statut général
        info_html += f"<p><strong>Statut:</strong> {self.status_badge(obj)}</p>"

        # Dates
        if obj.uploaded_at:
            info_html += f"<p><strong>Téléchargé:</strong> {obj.uploaded_at.strftime('%d/%m/%Y %H:%M')}</p>"

        if obj.processed_at:
            info_html += f"<p><strong>Traité:</strong> {obj.processed_at.strftime('%d/%m/%Y %H:%M')}</p>"
            if obj.uploaded_at:
                duration = obj.processed_at - obj.uploaded_at
                info_html += f"<p><strong>Durée:</strong> {duration.total_seconds():.1f}s</p>"

        # Statistiques
        if obj.status == 'completed':
            content_length = len(obj.extracted_content) if obj.extracted_content else 0
            formatted_length = len(obj.formatted_content) if obj.formatted_content else 0
            image_count = obj.images.count()

            info_html += f"<hr><h6>Statistiques:</h6>"
            info_html += f"<p><strong>Texte extrait:</strong> {content_length:,} caractères</p>"
            info_html += f"<p><strong>HTML généré:</strong> {formatted_length:,} caractères</p>"
            info_html += f"<p><strong>Images:</strong> {image_count}</p>"

            if hasattr(obj, 'format_info'):
                format_info = obj.format_info
                if format_info.fonts_used:
                    info_html += f"<p><strong>Polices:</strong> {len(format_info.fonts_used)}</p>"

        # Erreurs
        if obj.error_message:
            info_html += f"<hr><div class='alert alert-danger'><strong>Erreur:</strong><br>{obj.error_message}</div>"

        info_html += "</div>"

        return mark_safe(info_html)

    processing_info.short_description = 'Informations de traitement'

    def get_queryset(self, request):
        """Optimise les requêtes"""
        return super().get_queryset(request).select_related(
            'uploaded_by'
        ).prefetch_related('images')

    actions = ['reprocess_documents', 'export_to_html']

    def reprocess_documents(self, request, queryset):
        """Action pour retraiter les documents sélectionnés"""
        from .utils.document_processor import DocumentProcessor
        import threading

        count = 0
        for document in queryset:
            if document.status in ['error', 'completed']:
                document.status = 'pending'
                document.error_message = None
                document.save()

                # Lancer le traitement en arrière-plan
                thread = threading.Thread(
                    target=lambda: DocumentProcessor(document).process_document()
                )
                thread.daemon = True
                thread.start()
                count += 1

        self.message_user(
            request,
            f"{count} document{'s' if count > 1 else ''} en cours de retraitement."
        )

    reprocess_documents.short_description = "Retraiter les documents sélectionnés"

    def export_to_html(self, request, queryset):
        """Action pour exporter les documents en HTML"""
        # Cette action redirigerait vers une vue d'export groupé
        pass

    export_to_html.short_description = "Exporter en HTML (groupé)"


@admin.register(DocumentImage)
class DocumentImageAdmin(admin.ModelAdmin):
    list_display = [
        'image_thumbnail',
        'document_link',
        'image_name',
        'position_in_document',
        'dimensions',
        'image_size'
    ]

    list_filter = [
        'document__file_type',
        'document__status',
        'document__uploaded_at'
    ]

    search_fields = [
        'image_name',
        'document__title'
    ]

    readonly_fields = [
        'image_preview'
    ]

    def image_thumbnail(self, obj):
        """Affiche une miniature de l'image"""
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 4px;" />',
                obj.image.url
            )
        return '-'

    image_thumbnail.short_description = 'Aperçu'

    def document_link(self, obj):
        """Lien vers le document parent"""
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)

    document_link.short_description = 'Document'
    document_link.admin_order_field = 'document__title'

    def dimensions(self, obj):
        """Affiche les dimensions de l'image"""
        if obj.width and obj.height:
            return f"{obj.width} × {obj.height}"
        return '-'

    dimensions.short_description = 'Dimensions'

    def image_size(self, obj):
        """Affiche la taille du fichier image"""
        if obj.image:
            try:
                size = obj.image.size
                if size >= 1024 ** 2:
                    return f"{size / (1024 ** 2):.1f} MB"
                elif size >= 1024:
                    return f"{size / 1024:.1f} KB"
                else:
                    return f"{size} B"
            except:
                return '-'
        return '-'

    image_size.short_description = 'Taille'

    def image_preview(self, obj):
        """Affiche un aperçu plus grand de l'image"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 400px; max-height: 300px; border: 1px solid #ddd;" />',
                obj.image.url
            )
        return "Aucune image"

    image_preview.short_description = 'Aperçu de l\'image'


@admin.register(DocumentFormat)
class DocumentFormatAdmin(admin.ModelAdmin):
    list_display = [
        'document_link',
        'page_dimensions',
        'fonts_count',
        'has_features',
        'css_size'
    ]

    list_filter = [
        'has_headers',
        'has_footers',
        'has_tables',
        'has_images'
    ]

    search_fields = [
        'document__title'
    ]

    readonly_fields = [
        'css_preview'
    ]

    def document_link(self, obj):
        """Lien vers le document parent"""
        url = reverse('admin:documents_document_change', args=[obj.document.pk])
        return format_html('<a href="{}">{}</a>', url, obj.document.title)

    document_link.short_description = 'Document'

    def page_dimensions(self, obj):
        """Affiche les dimensions de la page"""
        if obj.page_width and obj.page_height:
            return f"{obj.page_width:.0f} × {obj.page_height:.0f}"
        return '-'

    page_dimensions.short_description = 'Dimensions'

    def fonts_count(self, obj):
        """Nombre de polices utilisées"""
        if obj.fonts_used:
            return len(obj.fonts_used)
        return 0

    fonts_count.short_description = 'Polices'

    def has_features(self, obj):
        """Affiche les fonctionnalités présentes"""
        features = []
        if obj.has_headers:
            features.append('<span class="badge bg-info">En-têtes</span>')
        if obj.has_footers:
            features.append('<span class="badge bg-info">Pieds</span>')
        if obj.has_tables:
            features.append('<span class="badge bg-success">Tableaux</span>')
        if obj.has_images:
            features.append('<span class="badge bg-warning">Images</span>')

        return format_html(' '.join(features)) if features else '-'

    has_features.short_description = 'Fonctionnalités'

    def css_size(self, obj):
        """Taille du CSS généré"""
        if obj.generated_css:
            size = len(obj.generated_css)
            if size >= 1024:
                return f"{size / 1024:.1f} KB"
            else:
                return f"{size} B"
        return '-'

    css_size.short_description = 'CSS'

    def css_preview(self, obj):
        """Aperçu du CSS généré"""
        if obj.generated_css:
            # Limiter l'aperçu à 1000 caractères
            css_preview = obj.generated_css[:1000]
            if len(obj.generated_css) > 1000:
                css_preview += '...'

            return format_html(
                '<pre style="background: #f8f9fa; padding: 10px; border-radius: 4px; max-height: 300px; overflow-y: auto;">{}</pre>',
                css_preview
            )
        return "Aucun CSS généré"

    css_preview.short_description = 'Aperçu CSS'


# Configuration du site d'administration
admin.site.site_header = "Doc Format - Administration"
admin.site.site_title = "Doc Format Admin"
admin.site.index_title = "Gestion des documents"