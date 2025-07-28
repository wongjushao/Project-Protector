// Project Protector - Decrypt JavaScript
class DecryptManager {
    constructor() {
        this.maskedFile = null;
        this.jsonFile = null;
        this.keyFile = null;
        this.filePickerOpen = false; // Prevent multiple file pickers

        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        // File upload areas
        this.maskedFileArea = document.getElementById('masked-file-area');
        this.jsonFileArea = document.getElementById('json-file-area');
        this.keyFileArea = document.getElementById('key-file-area');

        // File inputs
        this.maskedFileInput = document.getElementById('masked-file-input');
        this.jsonFileInput = document.getElementById('json-file-input');
        this.keyFileInput = document.getElementById('key-file-input');

        // Debug: Check if elements are found
        console.log('Elements found:', {
            maskedFileArea: !!this.maskedFileArea,
            jsonFileArea: !!this.jsonFileArea,
            keyFileArea: !!this.keyFileArea,
            maskedFileInput: !!this.maskedFileInput,
            jsonFileInput: !!this.jsonFileInput,
            keyFileInput: !!this.keyFileInput
        });
        
        // File info displays
        this.maskedFileInfo = document.getElementById('masked-file-info');
        this.jsonFileInfo = document.getElementById('json-file-info');
        this.keyFileInfo = document.getElementById('key-file-info');
        
        // Buttons and status
        this.decryptBtn = document.getElementById('decrypt-btn');
        this.newDecryptBtn = document.getElementById('new-decrypt-btn');
        this.uploadStatus = document.getElementById('upload-status');
        this.statusSection = document.getElementById('decrypt-status-section');
        this.statusMessages = document.getElementById('decrypt-status-messages');
        this.progressContainer = document.getElementById('decrypt-progress-container');
        this.progressFill = document.getElementById('decrypt-progress-fill');
        this.progressText = document.getElementById('decrypt-progress-text');
    }

    bindEvents() {
        // File upload area clicks - prevent multiple dialogs but allow normal behavior
        this.maskedFileArea.addEventListener('click', (e) => {
            console.log('Masked file area clicked, filePickerOpen:', this.filePickerOpen);
            if (!this.filePickerOpen) {
                this.filePickerOpen = true;
                console.log('Opening masked file picker');
                this.maskedFileInput.click();
                // Reset flag after a short delay
                setTimeout(() => {
                    this.filePickerOpen = false;
                    console.log('Reset filePickerOpen flag');
                }, 1000);
            } else {
                console.log('File picker already open, ignoring click');
            }
        });
        this.jsonFileArea.addEventListener('click', (e) => {
            if (!this.filePickerOpen) {
                this.filePickerOpen = true;
                this.jsonFileInput.click();
                setTimeout(() => { this.filePickerOpen = false; }, 1000);
            }
        });
        this.keyFileArea.addEventListener('click', (e) => {
            if (!this.filePickerOpen) {
                this.filePickerOpen = true;
                this.keyFileInput.click();
                setTimeout(() => { this.filePickerOpen = false; }, 1000);
            }
        });

        // File input changes - also reset file picker flag
        this.maskedFileInput.addEventListener('change', (e) => {
            this.filePickerOpen = false;
            this.handleMaskedFileSelect(e);
        });
        this.jsonFileInput.addEventListener('change', (e) => {
            this.filePickerOpen = false;
            this.handleJsonFileSelect(e);
        });
        this.keyFileInput.addEventListener('change', (e) => {
            this.filePickerOpen = false;
            this.handleKeyFileSelect(e);
        });

        // Reset file picker flag when user cancels (focus returns to window)
        this.maskedFileInput.addEventListener('cancel', () => { this.filePickerOpen = false; });
        this.jsonFileInput.addEventListener('cancel', () => { this.filePickerOpen = false; });
        this.keyFileInput.addEventListener('cancel', () => { this.filePickerOpen = false; });

        // Fallback: reset flag when window regains focus (user closed dialog)
        window.addEventListener('focus', () => {
            setTimeout(() => { this.filePickerOpen = false; }, 100);
        });

        // Drag and drop for all areas
        this.setupDragAndDrop(this.maskedFileArea, 'masked');
        this.setupDragAndDrop(this.jsonFileArea, 'json');
        this.setupDragAndDrop(this.keyFileArea, 'key');

        // Button events
        this.decryptBtn.addEventListener('click', () => this.decryptFiles());
        this.newDecryptBtn.addEventListener('click', () => this.startNewDecryption());
    }

    setupDragAndDrop(area, type) {
        area.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.add('dragover');
        });

        area.addEventListener('dragleave', (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.remove('dragover');
        });

        area.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            area.classList.remove('dragover');

            const files = Array.from(e.dataTransfer.files);
            if (files.length > 0) {
                this.handleFileByType(files[0], type);
            }
        });
    }

    handleFileByType(file, type) {
        switch (type) {
            case 'masked':
                this.handleMaskedFile(file);
                break;
            case 'json':
                this.handleJsonFile(file);
                break;
            case 'key':
                this.handleKeyFile(file);
                break;
        }
    }

    handleMaskedFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleMaskedFile(file);
        }
    }

    handleJsonFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleJsonFile(file);
        }
    }

    handleKeyFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.handleKeyFile(file);
        }
    }

    handleMaskedFile(file) {
        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'image/jpeg',
            'image/png',
            'text/plain',
            'text/csv'
        ];

        if (!allowedTypes.includes(file.type)) {
            this.showUploadMessage('Invalid masked file type. Please select a PDF, DOCX, image, or text file.', 'error');
            return;
        }

        this.maskedFile = file;
        this.updateFileDisplay(this.maskedFileInfo, file, 'fas fa-file-alt');
        this.updateDecryptButton();
        this.showUploadMessage('Masked file uploaded successfully.', 'success');
    }

    handleJsonFile(file) {
        if (file.type !== 'application/json' && !file.name.endsWith('.json')) {
            this.showUploadMessage('Invalid JSON file. Please select a .json file.', 'error');
            return;
        }

        this.jsonFile = file;
        this.updateFileDisplay(this.jsonFileInfo, file, 'fas fa-code');
        this.updateDecryptButton();
        this.showUploadMessage('JSON metadata file uploaded successfully.', 'success');
    }

    handleKeyFile(file) {
        if (!file.name.endsWith('.key')) {
            this.showUploadMessage('Invalid key file. Please select a .key file.', 'error');
            return;
        }

        this.keyFile = file;
        this.updateFileDisplay(this.keyFileInfo, file, 'fas fa-key');
        this.updateDecryptButton();
        this.showUploadMessage('Decryption key uploaded successfully.', 'success');
    }

    updateFileDisplay(container, file, iconClass) {
        container.style.display = 'block';
        container.innerHTML = `
            <div class="file-item">
                <div class="file-info">
                    <div class="file-icon">
                        <i class="${iconClass}"></i>
                    </div>
                    <div class="file-details">
                        <h4>${file.name}</h4>
                        <p>${this.formatFileSize(file.size)} • ${file.type || 'Key file'}</p>
                    </div>
                </div>
                <div style="color: var(--success-green);">
                    <i class="fas fa-check-circle"></i>
                </div>
            </div>
        `;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    updateDecryptButton() {
        const allFilesUploaded = this.maskedFile && this.jsonFile && this.keyFile;
        this.decryptBtn.disabled = !allFilesUploaded;
        
        if (allFilesUploaded) {
            this.showUploadMessage('All files uploaded! Ready to decrypt.', 'info');
        }
    }

    async decryptFiles() {
        if (!this.maskedFile || !this.jsonFile || !this.keyFile) {
            this.showUploadMessage('Please upload all three files before decrypting.', 'error');
            return;
        }

        this.setButtonLoading(this.decryptBtn, true);
        this.showStatusSection();
        this.showProgress(0, 'Preparing decryption...');

        try {
            const formData = new FormData();
            formData.append('masked_file', this.maskedFile);
            formData.append('json_file', this.jsonFile);
            formData.append('key_file', this.keyFile);

            this.showProgress(30, 'Uploading files for decryption...');

            const response = await fetch('/api/decrypt', {
                method: 'POST',
                body: formData
            });

            this.showProgress(70, 'Processing decryption...');

            if (!response.ok) {
                throw new Error(`Decryption failed: ${response.statusText}`);
            }

            this.showProgress(90, 'Preparing download...');

            // Handle file download
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = url;
            
            // Get filename from response headers or use default
            const contentDisposition = response.headers.get('content-disposition');
            let filename = 'decrypted_file';
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="(.+)"/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            } else {
                // Use original filename with 'decrypted_' prefix
                const originalName = this.maskedFile.name;
                const extension = originalName.substring(originalName.lastIndexOf('.'));
                const nameWithoutExt = originalName.substring(0, originalName.lastIndexOf('.'));
                filename = `decrypted_${nameWithoutExt}${extension}`;
            }
            
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(url);

            this.showProgress(100, 'Decryption completed successfully!');
            this.showStatusMessage('File decrypted successfully! Download should start automatically.', 'success');
            this.showNewDecryptButton();

        } catch (error) {
            this.showStatusMessage(`Decryption failed: ${error.message}`, 'error');
            this.hideProgress();
        } finally {
            this.setButtonLoading(this.decryptBtn, false);
        }
    }

    startNewDecryption() {
        // Reset state
        this.maskedFile = null;
        this.jsonFile = null;
        this.keyFile = null;
        
        // Reset UI
        this.maskedFileInfo.style.display = 'none';
        this.jsonFileInfo.style.display = 'none';
        this.keyFileInfo.style.display = 'none';
        
        // Reset file inputs
        this.maskedFileInput.value = '';
        this.jsonFileInput.value = '';
        this.keyFileInput.value = '';
        
        // Reset buttons and status
        this.updateDecryptButton();
        this.statusSection.style.display = 'none';
        this.newDecryptBtn.style.display = 'none';
        this.clearUploadMessages();
        this.clearStatusMessages();
        this.hideProgress();
    }

    // UI Helper Methods
    showStatusSection() {
        this.statusSection.style.display = 'block';
    }

    showNewDecryptButton() {
        this.newDecryptBtn.style.display = 'inline-flex';
    }

    showProgress(percentage, text) {
        this.progressContainer.style.display = 'block';
        this.progressFill.style.width = `${percentage}%`;
        this.progressText.textContent = text;
    }

    hideProgress() {
        this.progressContainer.style.display = 'none';
    }

    showUploadMessage(message, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message status-${type}`;
        
        const iconMap = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'info': 'fas fa-info-circle'
        };
        
        messageDiv.innerHTML = `
            <i class="${iconMap[type] || 'fas fa-info-circle'}"></i>
            ${message}
        `;
        
        this.uploadStatus.appendChild(messageDiv);
        
        // Auto-remove after 3 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 3000);
        }
    }

    showStatusMessage(message, type) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `status-message status-${type}`;
        
        const iconMap = {
            'success': 'fas fa-check-circle',
            'error': 'fas fa-exclamation-circle',
            'info': 'fas fa-info-circle'
        };
        
        messageDiv.innerHTML = `
            <i class="${iconMap[type] || 'fas fa-info-circle'}"></i>
            ${message}
        `;
        
        this.statusMessages.appendChild(messageDiv);
    }

    clearUploadMessages() {
        this.uploadStatus.innerHTML = '';
    }

    clearStatusMessages() {
        this.statusMessages.innerHTML = '';
    }

    setButtonLoading(button, loading) {
        if (loading) {
            button.disabled = true;
            button.classList.add('loading');
        } else {
            button.disabled = false;
            button.classList.remove('loading');
        }
    }
}

// Initialize the decrypt manager
const decryptManager = new DecryptManager();
