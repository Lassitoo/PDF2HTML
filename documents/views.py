from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
import threading
import json

from .models import Document, DocumentImage, DocumentFormat
from .forms import DocumentUploadForm, DocumentFilterForm
from .utils.document_processor import DocumentProcessor


def document_list(request):
    """Liste des documents avec filtres et pagination"""
    filter_form = DocumentFilterForm(request.GET)
    documents = Document.objects.all()

    # Si l'utilisateur n'est pas connecté, créer un utilisateur temporaire
    if not request.user.is_authenticated:
        from django.contrib.auth.models import User
        temp_user, created = User.objects.get_or_create(
            username='anonymous',
            defaults={'email': 'anonymous@example.com'}
        )
        # Filtrer par utilisateur temporaire ou permettre l'accès
        documents = documents.filter(uploaded_by=temp_user)
    else:
        documents = documents.filter(uploaded_by=request.user)

    # Appliquer les filtres
    if filter_form.is_valid():
        search = filter_form.cleaned_data.get('search')
        status = filter_form.cleaned_data.get('status')
        file_type = filter_form.cleaned_data.get('file_type')
        sort_by = filter_form.cleaned_data.get('sort_by')
        date_from = filter_form.cleaned_data.get('date_from')
        date_to = filter_form.cleaned_data.get('date_to')

        if search:
            documents = documents.filter(
                Q(title__icontains=search) |
                Q(description__icontains=search) |
                Q(extracted_content__icontains=search)
            )

        if status:
            documents = documents.filter(status=status)

        if file_type:
            documents = documents.filter(file_type=file_type)

        if date_from:
            documents = documents.filter(uploaded_at__date__gte=date_from)

        if date_to:
            documents = documents.filter(uploaded_at__date__lte=date_to)

        if sort_by:
            documents = documents.order_by(sort_by)

    # Pagination
    paginator = Paginator(documents, 12)
    page_number = request.GET.get('page')
    page_documents = paginator.get_page(page_number)

    context = {
        'documents': page_documents,
        'filter_form': filter_form,
        'total_documents': documents.count(),
    }

    return render(request, 'documents/document_list.html', context)


def document_upload(request):
    """Upload d'un nouveau document"""
    if request.method == 'POST':
        # Gérer l'utilisateur non connecté
        user = request.user if request.user.is_authenticated else None
        if not user:
            from django.contrib.auth.models import User
            user, created = User.objects.get_or_create(
                username='anonymous',
                defaults={'email': 'anonymous@example.com'}
            )

        form = DocumentUploadForm(request.POST, request.FILES, user=user)

        if form.is_valid():
            document = form.save()

            # Lancer le traitement en arrière-plan
            thread = threading.Thread(
                target=process_document_background,
                args=(document.id,)
            )
            thread.daemon = True
            thread.start()

            messages.success(
                request,
                f'Document "{document.title}" téléchargé avec succès. Le traitement est en cours...'
            )

            return redirect('documents:detail', pk=document.id)
        else:
            messages.error(request, 'Erreur lors du téléchargement. Veuillez corriger les erreurs ci-dessous.')
    else:
        form = DocumentUploadForm()

    return render(request, 'documents/upload.html', {'form': form})


def document_detail(request, pk):
    """Détail d'un document"""
    document = get_object_or_404(Document, pk=pk)

    # Vérifier les permissions (simplifiées pour la démo)
    if request.user.is_authenticated and document.uploaded_by != request.user:
        raise Http404("Document non trouvé")

    context = {
        'document': document,
        'images': document.images.all(),
        'format_info': getattr(document, 'format_info', None),
    }

    return render(request, 'documents/document_detail.html', context)


@require_http_methods(["GET"])
def document_status(request, pk):
    """API pour vérifier le statut de traitement d'un document"""
    document = get_object_or_404(Document, pk=pk)

    data = {
        'status': document.status,
        'processed_at': document.processed_at.isoformat() if document.processed_at else None,
        'error_message': document.error_message,
        'has_content': bool(document.extracted_content),
        'has_formatted_content': bool(document.formatted_content),
        'progress': get_processing_progress(document.status)
    }

    return JsonResponse(data)


@require_http_methods(["POST"])
def reprocess_document(request, pk):
    """Relance le traitement d'un document"""
    document = get_object_or_404(Document, pk=pk)

    # Vérifier les permissions
    if request.user.is_authenticated and document.uploaded_by != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)

    if document.status == 'processing':
        return JsonResponse({'error': 'Le document est déjà en cours de traitement'}, status=400)

    # Réinitialiser le statut
    document.status = 'pending'
    document.error_message = None
    document.processed_at = None
    document.save()

    # Lancer le traitement
    thread = threading.Thread(
        target=process_document_background,
        args=(document.id,)
    )
    thread.daemon = True
    thread.start()

    return JsonResponse({'success': True, 'message': 'Retraitement lancé'})


@require_http_methods(["DELETE"])
def delete_document(request, pk):
    """Supprime un document"""
    document = get_object_or_404(Document, pk=pk)

    # Vérifier les permissions
    if request.user.is_authenticated and document.uploaded_by != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)

    title = document.title
    document.delete()

    return JsonResponse({
        'success': True,
        'message': f'Document "{title}" supprimé avec succès'
    })


@require_http_methods(["GET"])
def download_original(request, pk):
    """Télécharge le fichier original"""
    document = get_object_or_404(Document, pk=pk)

    # Vérifier les permissions
    if request.user.is_authenticated and document.uploaded_by != request.user:
        raise Http404("Document non trouvé")

    try:
        response = HttpResponse(
            document.original_file.read(),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{document.original_file.name}"'
        return response
    except Exception as e:
        raise Http404("Fichier non trouvé")


@require_http_methods(["GET"])
def export_html(request, pk):
    """Exporte le contenu formaté en HTML"""
    document = get_object_or_404(Document, pk=pk)

    # Vérifier les permissions
    if request.user.is_authenticated and document.uploaded_by != request.user:
        raise Http404("Document non trouvé")

    if not document.formatted_content:
        raise Http404("Contenu formaté non disponible")

    # Générer le HTML complet
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{document.title}</title>
        <style>
        {getattr(document.format_info, 'generated_css', '') if hasattr(document, 'format_info') else ''}
        </style>
    </head>
    <body>
        {document.formatted_content}
    </body>
    </html>
    """

    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{document.title}.html"'

    return response


def process_document_background(document_id):
    """Traite un document en arrière-plan"""
    try:
        document = Document.objects.get(id=document_id)
        processor = DocumentProcessor(document)
        success = processor.process_document()

        if success:
            print(f"Document {document.title} traité avec succès")
        else:
            print(f"Erreur lors du traitement du document {document.title}")

    except Document.DoesNotExist:
        print(f"Document avec l'ID {document_id} non trouvé")
    except Exception as e:
        print(f"Erreur lors du traitement: {str(e)}")


def get_processing_progress(status):
    """Retourne le pourcentage de progression basé sur le statut"""
    progress_map = {
        'pending': 0,
        'processing': 50,
        'completed': 100,
        'error': 0
    }
    return progress_map.get(status, 0)


def home(request):
    """Page d'accueil"""
    # Statistiques rapides
    total_docs = Document.objects.count()
    processed_docs = Document.objects.filter(status='completed').count()
    processing_docs = Document.objects.filter(status='processing').count()
    error_docs = Document.objects.filter(status='error').count()

    # Documents récents
    recent_docs = Document.objects.order_by('-uploaded_at')[:5]

    context = {
        'total_docs': total_docs,
        'processed_docs': processed_docs,
        'processing_docs': processing_docs,
        'error_docs': error_docs,
        'recent_docs': recent_docs,
    }

    return render(request, 'documents/home.html', context)


# Add this function to your views.py

@require_http_methods(["POST"])
def save_document_edits(request, pk):
    """Save user edits to the document"""
    document = get_object_or_404(Document, pk=pk)
    
    # Check permissions
    if request.user.is_authenticated and document.uploaded_by != request.user:
        return JsonResponse({'error': 'Permission refusée'}, status=403)
    
    try:
        data = json.loads(request.body)
        formatted_content = data.get('formatted_content', '')
        extracted_content = data.get('extracted_content', '')
        
        if not formatted_content:
            return JsonResponse({'error': 'Contenu formaté manquant'}, status=400)
        
        # Update document with edited content
        document.formatted_content = formatted_content
        document.extracted_content = extracted_content
        
        # Update modification timestamp
        document.processed_at = timezone.now()
        document.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Modifications sauvegardées avec succès'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Données JSON invalides'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Erreur serveur: {str(e)}'}, status=500)