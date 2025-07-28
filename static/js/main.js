// Project Protector - Main JavaScript
class ProjectProtector {
    constructor() {
        this.selectedFiles = [];
        this.currentTaskId = null;
        this.currentStep = 'upload'; // upload, submitted, processing, completed
        this.selectedPiiCategories = ['NAMES', 'RACES', 'ORG_NAMES', 'STATUS', 'LOCATIONS', 'RELIGIONS']; // Default: all enabled

        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        // File upload elements
        this.fileUploadArea = document.getElementById('file-upload-area');
        this.fileInput = document.getElementById('file-input');
        this.fileList = document.getElementById('file-list');
        this.selectedFilesContainer = document.getElementById('selected-files');
        
        // Buttons
        this.submitBtn = document.getElementById('submit-btn');
        this.processBtn = document.getElementById('process-btn');
        this.downloadBtn = document.getElementById('download-btn');
        this.humanReviewBtn = document.getElementById('human-review-btn');
        this.newTaskBtn = document.getElementById('new-task-btn');
        
        // Status elements
        this.statusSection = document.getElementById('status-section');
        this.statusMessages = document.getElementById('status-messages');
        this.progressContainer = document.getElementById('progress-container');
        this.progressFill = document.getElementById('progress-fill');
        this.progressText = document.getElementById('progress-text');
        this.taskInfo = document.getElementById('task-info');
        this.taskIdDisplay = document.getElementById('task-id-display');
        this.filesCount = document.getElementById('files-count');
        this.taskStatus = document.getElementById('task-status');

        // PII selection elements
        this.piiSelectionSection = document.getElementById('pii-selection-section');
        this.piiCheckboxes = document.querySelectorAll('.pii-checkbox');
        this.selectAllBtn = document.getElementById('select-all-pii');
        this.deselectAllBtn = document.getElementById('deselect-all-pii');
    }

    bindEvents() {
        // File upload events
        this.fileUploadArea.addEventListener('click', () => this.fileInput.click());
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        
        // Drag and drop events
        this.fileUploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.fileUploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.fileUploadArea.addEventListener('drop', (e) => this.handleDrop(e));
        
        // Button events
        this.submitBtn.addEventListener('click', () => this.submitFiles());
        this.processBtn.addEventListener('click', () => this.processFiles());
        this.downloadBtn.addEventListener('click', () => this.downloadFiles());
        this.humanReviewBtn.addEventListener('click', () => this.openHumanReview());
        this.newTaskBtn.addEventListener('click', () => this.startNewTask());

        // PII selection events
        this.piiCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', () => this.updatePiiSelection());
        });
        this.selectAllBtn.addEventListener('click', () => this.selectAllPii());
        this.deselectAllBtn.addEventListener('click', () => this.deselectAllPii());
    }

    handleDragOver(e) {
        e.preventDefault();
        this.fileUploadArea.classList.add('dragover');
    }

    handleDragLeave(e) {
        e.preventDefault();
        this.fileUploadArea.classList.remove('dragover');
    }

    handleDrop(e) {
        e.preventDefault();
        this.fileUploadArea.classList.remove('dragover');
        const files = Array.from(e.dataTransfer.files);
        this.addFiles(files);
    }

    handleFileSelect(e) {
        const files = Array.from(e.target.files);
        this.addFiles(files);
    }

    addFiles(files) {
        const allowedTypes = [
            'application/pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            'text/csv',
            'text/plain',
            'image/jpeg',
            'image/png',
            'image/webp'
        ];

        files.forEach(file => {
            if (allowedTypes.includes(file.type)) {
                if (!this.selectedFiles.find(f => f.name === file.name && f.size === file.size)) {
                    this.selectedFiles.push(file);
                }
            } else {
                this.showMessage(`File "${file.name}" is not supported.`, 'error');
            }
        });

        this.updateFileList();
        this.updateSubmitButton();
    }

    removeFile(index) {
        this.selectedFiles.splice(index, 1);
        this.updateFileList();
        this.updateSubmitButton();
    }

    updateFileList() {
        if (this.selectedFiles.length === 0) {
            this.fileList.style.display = 'none';
            this.piiSelectionSection.style.display = 'none';
            return;
        }

        this.fileList.style.display = 'block';
        this.piiSelectionSection.style.display = 'block';
        this.selectedFilesContainer.innerHTML = '';

        this.selectedFiles.forEach((file, index) => {
            const fileItem = document.createElement('div');
            fileItem.className = 'file-item';

            const fileIcon = this.getFileIcon(file.type);
            const fileSize = this.formatFileSize(file.size);

            fileItem.innerHTML = `
                <div class="file-info">
                    <div class="file-icon">
                        <i class="${fileIcon}"></i>
                    </div>
                    <div class="file-details">
                        <h4>${file.name}</h4>
                        <p>${fileSize} • ${file.type}</p>
                    </div>
                </div>
                <button class="remove-file" onclick="protector.removeFile(${index})">
                    <i class="fas fa-times"></i>
                </button>
            `;

            this.selectedFilesContainer.appendChild(fileItem);
        });
    }

    getFileIcon(type) {
        const iconMap = {
            'application/pdf': 'fas fa-file-pdf',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'fas fa-file-word',
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'fas fa-file-excel',
            'text/csv': 'fas fa-file-csv',
            'text/plain': 'fas fa-file-alt',
            'image/jpeg': 'fas fa-file-image',
            'image/png': 'fas fa-file-image',
            'image/webp': 'fas fa-file-image'
        };
        return iconMap[type] || 'fas fa-file';
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    updateSubmitButton() {
        this.submitBtn.disabled = this.selectedFiles.length === 0;
    }

    async submitFiles() {
        if (this.selectedFiles.length === 0) return;

        this.setButtonLoading(this.submitBtn, true);
        this.showProgress(0, 'Uploading files...');

        try {
            const formData = new FormData();
            this.selectedFiles.forEach(file => {
                formData.append('files', file);
            });

            // Add PII selection data
            formData.append('enabled_pii_categories', JSON.stringify(this.selectedPiiCategories));

            const response = await fetch('/api/upload_files', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }

            const result = await response.json();
            this.currentTaskId = result.task_id;
            
            this.showProgress(100, 'Files uploaded successfully!');
            this.showMessage('Files uploaded successfully! You can now process them.', 'success');
            this.showMessage(this.getPiiSelectionSummary(), 'info');

            // Update UI state
            this.currentStep = 'submitted';
            this.updateTaskInfo();
            this.showStatusSection();
            this.showProcessButton();

        } catch (error) {
            this.showMessage(`Upload failed: ${error.message}`, 'error');
        } finally {
            this.setButtonLoading(this.submitBtn, false);
        }
    }

    async processFiles() {
        if (!this.currentTaskId) return;

        this.setButtonLoading(this.processBtn, true);
        this.showProgress(0, 'Processing files...');

        try {
            const response = await fetch(`/api/process/${this.currentTaskId}`, {
                method: 'POST'
            });

            if (!response.ok) {
                throw new Error(`Processing failed: ${response.statusText}`);
            }

            const result = await response.json();
            
            this.showProgress(100, 'Files processed successfully!');
            this.showMessage('Files processed successfully! You can now download the results.', 'success');
            
            // Update UI state
            this.currentStep = 'completed';
            this.updateTaskInfo();
            this.showDownloadButton();

        } catch (error) {
            this.showMessage(`Processing failed: ${error.message}`, 'error');
        } finally {
            this.setButtonLoading(this.processBtn, false);
        }
    }

    downloadFiles() {
        if (!this.currentTaskId) return;
        
        // Create download link
        const downloadUrl = `/api/download/${this.currentTaskId}`;
        const link = document.createElement('a');
        link.href = downloadUrl;
        link.download = `task_${this.currentTaskId}.zip`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        this.showMessage('Download started! Check your downloads folder.', 'success');
        this.showNewTaskButton();
    }

    startNewTask() {
        // Reset state
        this.selectedFiles = [];
        this.currentTaskId = null;
        this.currentStep = 'upload';
        
        // Reset UI
        this.updateFileList();
        this.updateSubmitButton();
        this.statusSection.style.display = 'none';
        this.hideAllButtons();
        this.clearMessages();
        this.hideProgress();
        
        // Reset file input
        this.fileInput.value = '';
    }

    // UI Helper Methods
    showStatusSection() {
        this.statusSection.style.display = 'block';
    }

    showProcessButton() {
        this.hideAllButtons();
        this.processBtn.style.display = 'inline-flex';
    }

    showDownloadButton() {
        this.hideAllButtons();
        this.downloadBtn.style.display = 'inline-flex';

        // Show Human Review button for JPEG/JPG files
        this.checkAndShowHumanReviewButton();
    }

    showNewTaskButton() {
        this.newTaskBtn.style.display = 'inline-flex';
    }

    hideAllButtons() {
        this.processBtn.style.display = 'none';
        this.downloadBtn.style.display = 'none';
        this.humanReviewBtn.style.display = 'none';
        this.newTaskBtn.style.display = 'none';
    }

    updateTaskInfo() {
        this.taskInfo.style.display = 'block';
        this.taskIdDisplay.textContent = this.currentTaskId;
        this.filesCount.textContent = this.selectedFiles.length;
        
        const statusMap = {
            'submitted': 'Uploaded - Ready to Process',
            'processing': 'Processing Files...',
            'completed': 'Processing Complete'
        };
        this.taskStatus.textContent = statusMap[this.currentStep] || 'Unknown';
    }

    showProgress(percentage, text) {
        this.progressContainer.style.display = 'block';
        this.progressFill.style.width = `${percentage}%`;
        this.progressText.textContent = text;
    }

    hideProgress() {
        this.progressContainer.style.display = 'none';
    }

    showMessage(message, type) {
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
        
        // Auto-remove after 5 seconds for success messages
        if (type === 'success') {
            setTimeout(() => {
                if (messageDiv.parentNode) {
                    messageDiv.parentNode.removeChild(messageDiv);
                }
            }, 5000);
        }
    }

    clearMessages() {
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

    // PII Selection Methods
    updatePiiSelection() {
        this.selectedPiiCategories = [];
        this.piiCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
                this.selectedPiiCategories.push(checkbox.value);
            }
            // Update visual state
            const label = checkbox.closest('.pii-checkbox-label');
            if (checkbox.checked) {
                label.classList.add('checked');
            } else {
                label.classList.remove('checked');
            }
        });

        console.log('Selected PII categories:', this.selectedPiiCategories);
    }

    selectAllPii() {
        this.piiCheckboxes.forEach(checkbox => {
            checkbox.checked = true;
        });
        this.updatePiiSelection();
    }

    deselectAllPii() {
        this.piiCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });
        this.updatePiiSelection();
    }

    getPiiSelectionSummary() {
        const total = this.piiCheckboxes.length;
        const selected = this.selectedPiiCategories.length;

        if (selected === 0) {
            return "No optional PII types selected for masking";
        } else if (selected === total) {
            return "All optional PII types selected for masking";
        } else {
            return `${selected} of ${total} optional PII types selected for masking`;
        }
    }

    checkAndShowHumanReviewButton() {
        // Check if any processed files are JPEG/JPG
        if (!this.currentTaskId) return;

        // Get the list of processed files and check for JPEG/JPG
        const hasJpegFiles = this.selectedFiles.some(file => {
            const ext = file.name.toLowerCase();
            return ext.endsWith('.jpg') || ext.endsWith('.jpeg');
        });

        if (hasJpegFiles) {
            this.humanReviewBtn.style.display = 'inline-flex';
        }
    }

    openHumanReview() {
        if (!this.currentTaskId) {
            this.addStatusMessage('No task ID available for human review', 'error');
            return;
        }

        // Find the first JPEG/JPG file for review
        const jpegFile = this.selectedFiles.find(file => {
            const ext = file.name.toLowerCase();
            return ext.endsWith('.jpg') || ext.endsWith('.jpeg');
        });

        if (!jpegFile) {
            this.addStatusMessage('No JPEG/JPG files available for human review', 'error');
            return;
        }

        // Open human review page
        const reviewUrl = `/human-review/${this.currentTaskId}/${jpegFile.name}`;
        window.open(reviewUrl, '_blank');

        this.addStatusMessage(`Opening human review for ${jpegFile.name}`, 'success');
    }
}

// Initialize the application
const protector = new ProjectProtector();
