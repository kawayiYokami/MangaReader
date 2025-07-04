const mangaBrowser = {
    init() {
        this.cacheDOMElements();
        this.bindEventListeners();
        this.loadMangaData();
    },

    cacheDOMElements() {
        this.gridContainer = document.getElementById('manga-grid-container');
        this.loadingIndicator = document.getElementById('loading-indicator');
        this.scanButton = document.getElementById('scan-button');
        this.scanDialog = document.getElementById('scan-dialog');
        this.selectFolderButton = document.getElementById('select-folder-button');
        this.startScanButton = document.getElementById('start-scan-button');
        this.cancelScanButton = this.scanDialog.querySelector('.cancel-button');
        this.scanPathInput = document.getElementById('scan-path-input');
        this.forceRescanCheckbox = document.getElementById('force-rescan-checkbox');
    },

    bindEventListeners() {
        this.scanButton.addEventListener('click', () => this.showScanDialog());
        this.cancelScanButton.addEventListener('click', () => this.hideScanDialog());
        this.selectFolderButton.addEventListener('click', () => this.selectDirectory());
        this.startScanButton.addEventListener('click', () => this.startScan());
    },

    async loadMangaData() {
        this.showLoading();
        try {
            const response = await fetch('/api/manga/');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const mangaList = await response.json();
            this.renderMangaGrid(mangaList);
        } catch (error) {
            console.error("Failed to load manga data:", error);
            this.gridContainer.innerHTML = '<p class="error">Failed to load manga library. See console for details.</p>';
        } finally {
            this.hideLoading();
        }
    },

    renderMangaGrid(mangaList) {
        this.gridContainer.innerHTML = ''; // Clear existing content
        if (mangaList.length === 0) {
            this.gridContainer.innerHTML = '<p>No manga found. Try scanning a directory.</p>';
            return;
        }

        mangaList.forEach(manga => {
            const card = document.createElement('div');
            card.className = 'manga-card';
            card.dataset.mangaId = manga.manga_id;
            
            const coverUrl = `/api/manga/${manga.manga_id}/cover`;

            card.innerHTML = `
                <div class="manga-card-cover">
                    <img src="${coverUrl}" alt="${manga.title}" loading="lazy">
                </div>
                <div class="manga-card-title">${manga.title}</div>
            `;
            
            card.addEventListener('click', () => {
                // In a desktop app context, we might use the JS bridge to open a new window
                if (window.pywebview && window.pywebview.api.manga_viewer_manager) {
                     window.pywebview.api.manga_viewer_manager.open_viewer(manga.manga_id);
                } else {
                    // Fallback for standard web browser
                    window.open(`/viewer?manga_id=${manga.manga_id}`, '_blank');
                }
            });

            this.gridContainer.appendChild(card);
        });
    },

    showLoading() {
        this.loadingIndicator.classList.remove('hidden');
    },

    hideLoading() {
        this.loadingIndicator.classList.add('hidden');
    },

    showScanDialog() {
        this.scanDialog.classList.remove('hidden');
    },

    hideScanDialog() {
        this.scanDialog.classList.add('hidden');
    },

    async selectDirectory() {
        // This requires the pywebview JS bridge
        if (window.pywebview && window.pywebview.api.open_folder_dialog) {
            try {
                const result = await window.pywebview.api.open_folder_dialog();
                if (result && result.path) {
                    this.scanPathInput.value = result.path;
                }
            } catch (e) {
                console.error("Error opening folder dialog:", e);
                showToast("Could not open folder dialog.", "error");
            }
        } else {
            showToast("This feature is only available in the desktop app.", "warning");
        }
    },

    async startScan() {
        const path = this.scanPathInput.value;
        if (!path) {
            showToast("Please select a directory to scan.", "error");
            return;
        }

        const force = this.forceRescanCheckbox.checked;
        
        try {
            const response = await fetch('/api/manga/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ path, force }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Failed to start scan.");
            }

            showToast("Manga scan started in the background.", "info");
            this.hideScanDialog();
        } catch (error) {
            console.error("Error starting scan:", error);
            showToast(error.message, "error");
        }
    }
};

// Expose the mangaBrowser object to the global window scope
window.mangaBrowser = mangaBrowser;