// documents/js/script.js
/**
 * Doc Format - JavaScript principal
 * Gestion des interactions côté client + viewer PDF fidèle
 */

(function () {
  "use strict";

  // =========================
  //  Boot & Core UI Behaviors
  // =========================
  document.addEventListener("DOMContentLoaded", function () {
    initializeComponents();
    setupEventListeners();
    applyAnimations();
    initPdfViewer(); // <= Active la gestion de zoom/fit PDF
  });

  /**
   * Initialise les composants JavaScript
   */
  function initializeComponents() {
    // Initialiser les tooltips Bootstrap
    initializeTooltips();

    // Initialiser les popovers Bootstrap
    initializePopovers();

    // Auto-dismiss des alertes
    setupAlertAutoDismiss();

    // Gestion du thème
    initializeTheme();
  }

  /**
   * Configure les événements
   */
  function setupEventListeners() {
    // Gestion des formulaires
    setupFormValidation();

    // Gestion du drag & drop
    setupDragAndDrop();

    // Gestion des confirmations
    setupConfirmationDialogs();

    // Gestion du scroll
    setupScrollEffects();

    // Recherche en temps réel
    setupLiveSearch();
  }

  /**
   * Applique les animations
   */
  function applyAnimations() {
    const elementsToAnimate = document.querySelectorAll(".card, .alert, .btn");
    elementsToAnimate.forEach((element, index) => {
      element.style.animationDelay = `${index * 0.1}s`;
      element.classList.add("fade-in-up");
    });
  }

  /**
   * Initialise les tooltips Bootstrap
   */
  function initializeTooltips() {
    const tooltipTriggerList = [].slice.call(
      document.querySelectorAll("[data-bs-toggle='tooltip']")
    );
    tooltipTriggerList.map(function (tooltipTriggerEl) {
      return new bootstrap.Tooltip(tooltipTriggerEl);
    });
  }

  /**
   * Initialise les popovers Bootstrap
   */
  function initializePopovers() {
    const popoverTriggerList = [].slice.call(
      document.querySelectorAll("[data-bs-toggle='popover']")
    );
    popoverTriggerList.map(function (popoverTriggerEl) {
      return new bootstrap.Popover(popoverTriggerEl);
    });
  }

  /**
   * Configure la disparition automatique des alertes
   */
  function setupAlertAutoDismiss() {
    const alerts = document.querySelectorAll(".alert:not(.alert-permanent)");
    alerts.forEach((alert) => {
      if (!alert.classList.contains("alert-danger")) {
        setTimeout(() => {
          try {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
          } catch (e) {}
        }, 5000);
      }
    });
  }

  /**
   * Gestion du thème (mode sombre/clair)
   */
  function initializeTheme() {
    const themeToggle = document.getElementById("theme-toggle");
    if (themeToggle) {
      const currentTheme = localStorage.getItem("theme") || "light";
      document.documentElement.setAttribute("data-theme", currentTheme);

      themeToggle.addEventListener("click", function () {
        const theme =
          document.documentElement.getAttribute("data-theme") === "dark"
            ? "light"
            : "dark";
        document.documentElement.setAttribute("data-theme", theme);
        localStorage.setItem("theme", theme);
      });
    }
  }

  /**
   * Validation des formulaires en temps réel
   */
  function setupFormValidation() {
    const forms = document.querySelectorAll(".needs-validation");

    forms.forEach((form) => {
      form.addEventListener("submit", function (event) {
        if (!form.checkValidity()) {
          event.preventDefault();
          event.stopPropagation();

          const firstInvalid = form.querySelector(":invalid");
          if (firstInvalid) {
            firstInvalid.scrollIntoView({ behavior: "smooth", block: "center" });
            firstInvalid.focus();
          }
        }
        form.classList.add("was-validated");
      });

      const inputs = form.querySelectorAll("input, select, textarea");
      inputs.forEach((input) => {
        input.addEventListener("blur", function () {
          if (form.classList.contains("was-validated")) {
            validateField(input);
          }
        });

        input.addEventListener("input", function () {
          if (form.classList.contains("was-validated")) {
            clearTimeout(input.validationTimeout);
            input.validationTimeout = setTimeout(() => {
              validateField(input);
            }, 300);
          }
        });
      });
    });
  }

  function validateField(field) {
    const isValid = field.checkValidity();
    const feedback = field.parentNode.querySelector(".invalid-feedback");

    if (isValid) {
      field.classList.remove("is-invalid");
      field.classList.add("is-valid");
    } else {
      field.classList.remove("is-valid");
      field.classList.add("is-invalid");

      if (feedback) {
        feedback.textContent = field.validationMessage;
      }
    }
  }

  /**
   * Configuration du drag & drop pour les fichiers
   */
  function setupDragAndDrop() {
    const dropZones = document.querySelectorAll(".drop-zone");

    dropZones.forEach((dropZone) => {
      const fileInput = dropZone.querySelector('input[type="file"]');
      if (!fileInput) return;

      ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
      });

      ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, highlight, false);
      });

      ["dragleave", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, unhighlight, false);
      });

      dropZone.addEventListener("drop", handleDrop, false);

      function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
      }

      function highlight() {
        dropZone.classList.add("dragover");
      }

      function unhighlight() {
        dropZone.classList.remove("dragover");
      }

      function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
          fileInput.files = files;

          const event = new Event("change", { bubbles: true });
          fileInput.dispatchEvent(event);

          showFileDropSuccess(dropZone, files[0]);
        }
      }
    });
  }

  function showFileDropSuccess(dropZone, file) {
    const originalContent = dropZone.innerHTML;
    dropZone.innerHTML = `
      <div class="text-success">
        <i class="bi bi-check-circle display-4 mb-3"></i>
        <h4>Fichier ajouté avec succès!</h4>
        <p class="mb-0">${file.name} (${formatFileSize(file.size)})</p>
      </div>
    `;
    dropZone.classList.add("pulse-animation");
    setTimeout(() => {
      dropZone.innerHTML = originalContent;
      dropZone.classList.remove("pulse-animation");
    }, 2000);
  }

  /**
   * Dialogues de confirmation
   */
  function setupConfirmationDialogs() {
    const confirmButtons = document.querySelectorAll("[data-confirm]");
    confirmButtons.forEach((button) => {
      button.addEventListener("click", function (e) {
        const message = this.getAttribute("data-confirm");
        if (!confirm(message)) {
          e.preventDefault();
          e.stopPropagation();
          return false;
        }
      });
    });
  }

  /**
   * Effets de scroll
   */
  function setupScrollEffects() {
    let ticking = false;

    function updateScrollEffects() {
      const scrolled = window.scrollY;
      const navbar = document.querySelector(".navbar");

      if (navbar) {
        if (scrolled > 50) {
          navbar.classList.add("scrolled");
        } else {
          navbar.classList.remove("scrolled");
        }
      }

      const elementsToReveal = document.querySelectorAll(".reveal-on-scroll");
      elementsToReveal.forEach((element) => {
        const elementTop = element.getBoundingClientRect().top;
        const elementVisible = 150;

        if (elementTop < window.innerHeight - elementVisible) {
          element.classList.add("revealed");
        }
      });

      ticking = false;
    }

    window.addEventListener("scroll", function () {
      if (!ticking) {
        requestAnimationFrame(updateScrollEffects);
        ticking = true;
      }
    });
  }

  /**
   * Recherche live (placeholder)
   */
  function setupLiveSearch() {
    const searchInputs = document.querySelectorAll(".live-search");

    searchInputs.forEach((input) => {
      let searchTimeout;

      input.addEventListener("input", function () {
        clearTimeout(searchTimeout);
        const query = this.value.trim();

        if (query.length === 0) {
          clearSearchResults();
          return;
        }

        searchTimeout = setTimeout(() => {
          performLiveSearch(query);
        }, 300);
      });
    });
  }

  function performLiveSearch(query) {
    const searchResults = document.getElementById("search-results");
    if (!searchResults) return;
    searchResults.innerHTML =
      '<div class="text-center"><div class="spinner-border" role="status"></div></div>';

    setTimeout(() => {
      searchResults.innerHTML = `
        <div class="alert alert-info">
          Résultats pour "${query}" - Fonctionnalité à implémenter
        </div>
      `;
    }, 500);
  }

  function clearSearchResults() {
    const searchResults = document.getElementById("search-results");
    if (searchResults) searchResults.innerHTML = "";
  }

  // =========================
  //        Utils (Core)
  // =========================
  function formatFileSize(bytes) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction() {
      const context = this;
      const args = arguments;
      const later = function () {
        timeout = null;
        if (!immediate) func.apply(context, args);
      };
      const callNow = immediate && !timeout;
      clearTimeout(timeout);
      timeout = setTimeout(later, wait);
      if (callNow) func.apply(context, args);
    };
  }

  // Gestion erreurs globales
  window.addEventListener("error", function (e) {
    console.error("Erreur JavaScript:", e.error);
  });
  window.addEventListener("unhandledrejection", function (e) {
    console.error("Promise rejetée:", e.reason);
  });

  // AJAX helpers
  const API = {
    get: async function (url) {
      try {
        const response = await fetch(url, {
          method: "GET",
          headers: { "Content-Type": "application/json" },
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
      } catch (error) {
        console.error("Erreur GET:", error);
        throw error;
      }
    },
    post: async function (url, data) {
      try {
        const response = await fetch(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": this.getCSRFToken(),
          },
          body: JSON.stringify(data),
        });
        if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
        return await response.json();
      } catch (error) {
        console.error("Erreur POST:", error);
        throw error;
      }
    },
    getCSRFToken: function () {
      const cookieValue = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrftoken="));
      if (cookieValue) return cookieValue.split("=")[1];
      const csrfInput = document.querySelector("[name=csrfmiddlewaretoken]");
      return csrfInput ? csrfInput.value : "";
    },
  };

  // =========================
  //     PDF Viewer Fidelity
  // =========================
  const PDF_ZOOM_KEY = "pdf_zoom";
  let currentZoom = 1;

  function initPdfViewer() {
    // Restore saved zoom
    const saved = parseFloat(localStorage.getItem(PDF_ZOOM_KEY) || "1");
    if (!isNaN(saved) && saved > 0) {
      currentZoom = saved;
      applyZoom(currentZoom);
    }

    // Ctrl/Cmd + Wheel for zoom
    const wrapper = document.querySelector(".document-content-wrapper") || document;
    wrapper.addEventListener(
      "wheel",
      function (e) {
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault();
          const delta = Math.sign(e.deltaY);
          if (delta > 0) zoomBy(0.9); // zoom out
          else zoomBy(1.1); // zoom in
        }
      },
      { passive: false }
    );

    // Keyboard shortcuts: Ctrl/Cmd + '+', '-', '0'
    document.addEventListener("keydown", function (e) {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === "+" || e.key === "=") {
          e.preventDefault();
          zoomBy(1.1);
        } else if (e.key === "-") {
          e.preventDefault();
          zoomBy(0.9);
        } else if (e.key === "0") {
          e.preventDefault();
          setZoom(1);
        }
      }
    });

    // Expose helper fits (optional usage)
    window.DocFormat.fitToWidth = fitToWidth;
    window.DocFormat.fitToPageHeight = fitToPageHeight;
  }

  function applyZoom(scale) {
    const pages = document.querySelectorAll(".pdf-page");
    pages.forEach((pg) => {
      pg.style.transform = `scale(${scale})`;
      pg.style.transformOrigin = "top center";
    });
    localStorage.setItem(PDF_ZOOM_KEY, String(scale));
  }

  function setZoom(scale) {
    if (!scale || scale <= 0) return;
    currentZoom = clamp(scale, 0.3, 4);
    applyZoom(currentZoom);
  }

  function zoomBy(factor) {
    const next = currentZoom * factor;
    setZoom(next);
  }

  function fitToWidth() {
    const container =
      document.querySelector(".document-preview-container") ||
      document.querySelector(".pdf-document-container") ||
      document.body;

    const firstPage = document.querySelector(".pdf-page");
    if (!firstPage) return;

    // largeur visible dispo
    const available =
      container.clientWidth -
      parseFloat(getComputedStyle(container).paddingLeft || "0") -
      parseFloat(getComputedStyle(container).paddingRight || "0") -
      2; // marge anti scroll

    // largeur réelle de la page sans zoom
    const pageRect = firstPage.getBoundingClientRect();
    // Pour obtenir la largeur "naturelle" sans zoom, on retire le scale courant
    const naturalWidth = pageRect.width / currentZoom;

    if (naturalWidth > 0) {
      const scale = clamp(available / naturalWidth, 0.3, 4);
      setZoom(scale);
    }
  }

  function fitToPageHeight() {
    const container =
      document.querySelector(".document-preview-container") ||
      document.querySelector(".pdf-document-container") ||
      document.body;

    const firstPage = document.querySelector(".pdf-page");
    if (!firstPage) return;

    const available =
      container.clientHeight -
      parseFloat(getComputedStyle(container).paddingTop || "0") -
      parseFloat(getComputedStyle(container).paddingBottom || "0") -
      2;

    const pageRect = firstPage.getBoundingClientRect();
    const naturalHeight = pageRect.height / currentZoom;

    if (naturalHeight > 0) {
      const scale = clamp(available / naturalHeight, 0.3, 4);
      setZoom(scale);
    }
  }

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  // ==========
  //  Exports
  // ==========
  window.DocFormat = Object.assign(window.DocFormat || {}, {
    formatFileSize,
    copyToClipboard,
    API,
    debounce,
    setZoom,     // DocFormat.setZoom(1.2)
    zoomBy,      // DocFormat.zoomBy(1.1)
    fitToWidth,  // DocFormat.fitToWidth()
    fitToPageHeight, // DocFormat.fitToPageHeight()
  });

  // Garde compatibilité avec ton HTML existant: <button onclick="zoomDocument(1.2)">
  window.zoomDocument = function (absoluteScale) {
    // le HTML existant passe une valeur absolue (0.8, 1, 1.2)
    if (!absoluteScale || absoluteScale <= 0) return;
    setZoom(absoluteScale);
  };

  /**
   * Copie utilitaire (déjà exportée via window.DocFormat)
   */
  function copyToClipboard(text, button = null) {
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard
        .writeText(text)
        .then(() => {
          showCopySuccess(button);
        })
        .catch((err) => {
          console.error("Erreur lors de la copie:", err);
          fallbackCopyTextToClipboard(text, button);
        });
    } else {
      fallbackCopyTextToClipboard(text, button);
    }
  }

  function fallbackCopyTextToClipboard(text, button = null) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.position = "fixed";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();

    try {
      document.execCommand("copy");
      showCopySuccess(button);
    } catch (err) {
      console.error("Erreur lors de la copie:", err);
    }
    document.body.removeChild(textArea);
  }

  function showCopySuccess(button) {
    if (button) {
      const originalContent = button.innerHTML;
      button.innerHTML = '<i class="bi bi-check"></i> Copié!';
      button.classList.add("btn-success");
      setTimeout(() => {
        button.innerHTML = originalContent;
        button.classList.remove("btn-success");
      }, 2000);
    }
  }

  // (Optionnel) Service Worker
  if ("serviceWorker" in navigator && "production" === "production") {
    window.addEventListener("load", function () {
      navigator.serviceWorker
        .register("/sw.js")
        .then(function (registration) {
          console.log("SW registered: ", registration);
        })
        .catch(function (registrationError) {
          console.log("SW registration failed: ", registrationError);
        });
    });
  }
})();
