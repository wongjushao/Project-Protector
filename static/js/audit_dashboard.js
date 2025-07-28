// static/js/audit_dashboard.js
class AuditDashboard {
    constructor() {
        this.currentTab = 'file-operations';
        this.currentPage = 0;
        this.pageSize = 50;
        this.refreshInterval = 30000; // 30 seconds
        this.autoRefreshEnabled = true;
        
        this.initializeEventListeners();
        this.loadInitialData();
        this.startAutoRefresh();
    }
    
    initializeEventListeners() {
        // Tab switching
        document.querySelectorAll('.tab-button').forEach(button => {
            button.addEventListener('click', (e) => {
                this.switchTab(e.target.dataset.tab);
            });
        });
        
        // Refresh button
        document.getElementById('refresh-all').addEventListener('click', () => {
            this.refreshAllData();
        });
        
        // Filter change listeners
        document.getElementById('file-op-type-filter')?.addEventListener('change', () => {
            this.loadFileOperations();
        });
        
        document.getElementById('file-status-filter')?.addEventListener('change', () => {
            this.loadFileOperations();
        });
        
        document.getElementById('action-type-filter')?.addEventListener('change', () => {
            this.loadUserActions();
        });
        
        document.getElementById('event-type-filter')?.addEventListener('change', () => {
            this.loadSystemEvents();
        });
        
        document.getElementById('severity-filter')?.addEventListener('change', () => {
            this.loadSystemEvents();
        });
        
        document.getElementById('active-sessions-only')?.addEventListener('change', () => {
            this.loadSessions();
        });
    }
    
    async loadInitialData() {
        try {
            await this.loadStatistics();
            await this.loadCurrentTabData();
        } catch (error) {
            console.error('Failed to load initial data:', error);
            this.showError('Failed to load dashboard data');
        }
    }
    
    async loadStatistics() {
        try {
            const response = await fetch('/api/audit/statistics?days=30');
            const result = await response.json();
            
            if (result.success) {
                this.updateStatistics(result.data);
                document.getElementById('last-updated').textContent = 
                    `Last updated: ${new Date().toLocaleString()}`;
            }
        } catch (error) {
            console.error('Failed to load statistics:', error);
        }
    }
    
    updateStatistics(stats) {
        document.getElementById('total-sessions').textContent = 
            stats.file_operations?.total || 0;
        document.getElementById('total-uploads').textContent = 
            stats.file_operations?.uploads || 0;
        document.getElementById('total-processed').textContent = 
            stats.file_operations?.processes || 0;
        document.getElementById('total-pii-masked').textContent = 
            stats.pii_processing?.total_pii_masked || 0;
        document.getElementById('total-errors').textContent = 
            stats.system_events?.errors || 0;
        document.getElementById('avg-processing-time').textContent = 
            `${(stats.pii_processing?.average_processing_time || 0).toFixed(2)}s`;
    }
    
    switchTab(tabName) {
        // Update tab buttons
        document.querySelectorAll('.tab-button').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
        
        // Update tab content
        document.querySelectorAll('.tab-content').forEach(content => {
            content.classList.remove('active');
        });
        document.getElementById(tabName).classList.add('active');
        
        this.currentTab = tabName;
        this.currentPage = 0;
        this.loadCurrentTabData();
    }
    
    async loadCurrentTabData() {
        switch (this.currentTab) {
            case 'file-operations':
                await this.loadFileOperations();
                break;
            case 'pii-processing':
                await this.loadPIIProcessing();
                break;
            case 'user-actions':
                await this.loadUserActions();
                break;
            case 'system-events':
                await this.loadSystemEvents();
                break;
            case 'sessions':
                await this.loadSessions();
                break;
        }
    }
    
    async loadFileOperations() {
        try {
            const operationType = document.getElementById('file-op-type-filter')?.value || '';
            const status = document.getElementById('file-status-filter')?.value || '';
            
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: this.currentPage * this.pageSize
            });
            
            if (operationType) params.append('operation_type', operationType);
            if (status) params.append('status', status);
            
            const response = await fetch(`/api/audit/file-operations?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderFileOperations(result.data);
            }
        } catch (error) {
            console.error('Failed to load file operations:', error);
            this.showError('Failed to load file operations');
        }
    }
    
    renderFileOperations(data) {
        const container = document.getElementById('file-operations-content');
        
        if (!data.operations || data.operations.length === 0) {
            container.innerHTML = '<div class="loading">No file operations found</div>';
            return;
        }
        
        const table = `
            <table class="audit-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Operation</th>
                        <th>File Name</th>
                        <th>File Type</th>
                        <th>Size</th>
                        <th>PII Categories</th>
                        <th>Processing Time</th>
                        <th>Status</th>
                        <th>IP Address</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.operations.map(op => `
                        <tr>
                            <td class="timestamp">${this.formatTimestamp(op.timestamp)}</td>
                            <td><span class="status-badge status-info">${op.operation_type}</span></td>
                            <td>${op.file_name}</td>
                            <td>${op.file_type}</td>
                            <td>${this.formatFileSize(op.file_size)}</td>
                            <td>${op.total_pii_categories || 0} categories</td>
                            <td>${op.processing_time_seconds ? op.processing_time_seconds.toFixed(2) + 's' : '-'}</td>
                            <td><span class="status-badge status-${op.status}">${op.status}</span></td>
                            <td>${op.ip_address}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${this.renderPagination(data.total, data.offset, data.limit)}
        `;
        
        container.innerHTML = table;
    }
    
    async loadPIIProcessing() {
        try {
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: this.currentPage * this.pageSize
            });
            
            const response = await fetch(`/api/audit/pii-processing?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderPIIProcessing(result.data);
            }
        } catch (error) {
            console.error('Failed to load PII processing:', error);
            this.showError('Failed to load PII processing logs');
        }
    }
    
    renderPIIProcessing(data) {
        const container = document.getElementById('pii-processing-content');
        
        if (!data.processing_logs || data.processing_logs.length === 0) {
            container.innerHTML = '<div class="loading">No PII processing logs found</div>';
            return;
        }
        
        const table = `
            <table class="audit-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>PII Found</th>
                        <th>PII Masked</th>
                        <th>Processing Time</th>
                        <th>Avg Confidence</th>
                        <th>Selectable PII</th>
                        <th>Non-Selectable PII</th>
                        <th>Masked Categories</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.processing_logs.map(log => `
                        <tr>
                            <td class="timestamp">${this.formatTimestamp(log.timestamp)}</td>
                            <td>${log.total_pii_found}</td>
                            <td>${log.total_pii_masked}</td>
                            <td>${log.processing_time_seconds ? log.processing_time_seconds.toFixed(2) + 's' : '-'}</td>
                            <td>${log.average_confidence ? (log.average_confidence * 100).toFixed(1) + '%' : '-'}</td>
                            <td class="json-data">${JSON.stringify(log.selectable_pii_found || {})}</td>
                            <td class="json-data">${JSON.stringify(log.non_selectable_pii_found || {})}</td>
                            <td class="json-data">${JSON.stringify(log.masked_categories || [])}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${this.renderPagination(data.total, data.offset, data.limit)}
        `;
        
        container.innerHTML = table;
    }
    
    async loadUserActions() {
        try {
            const actionType = document.getElementById('action-type-filter')?.value || '';
            
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: this.currentPage * this.pageSize
            });
            
            if (actionType) params.append('action_type', actionType);
            
            const response = await fetch(`/api/audit/user-actions?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderUserActions(result.data);
            }
        } catch (error) {
            console.error('Failed to load user actions:', error);
            this.showError('Failed to load user actions');
        }
    }
    
    renderUserActions(data) {
        const container = document.getElementById('user-actions-content');
        
        if (!data.actions || data.actions.length === 0) {
            container.innerHTML = '<div class="loading">No user actions found</div>';
            return;
        }
        
        const table = `
            <table class="audit-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Action Type</th>
                        <th>Action Name</th>
                        <th>Method</th>
                        <th>Endpoint</th>
                        <th>Response Status</th>
                        <th>Response Time</th>
                        <th>IP Address</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.actions.map(action => `
                        <tr>
                            <td class="timestamp">${this.formatTimestamp(action.timestamp)}</td>
                            <td><span class="status-badge status-info">${action.action_type}</span></td>
                            <td>${action.action_name}</td>
                            <td>${action.http_method || '-'}</td>
                            <td>${action.endpoint || '-'}</td>
                            <td><span class="status-badge ${this.getStatusClass(action.response_status)}">${action.response_status || '-'}</span></td>
                            <td>${action.response_time_ms ? action.response_time_ms.toFixed(0) + 'ms' : '-'}</td>
                            <td>${action.ip_address}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${this.renderPagination(data.total, data.offset, data.limit)}
        `;
        
        container.innerHTML = table;
    }
    
    async loadSystemEvents() {
        try {
            const eventType = document.getElementById('event-type-filter')?.value || '';
            const severity = document.getElementById('severity-filter')?.value || '';
            
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: this.currentPage * this.pageSize
            });
            
            if (eventType) params.append('event_type', eventType);
            if (severity) params.append('severity_level', severity);
            
            const response = await fetch(`/api/audit/system-events?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderSystemEvents(result.data);
            }
        } catch (error) {
            console.error('Failed to load system events:', error);
            this.showError('Failed to load system events');
        }
    }
    
    renderSystemEvents(data) {
        const container = document.getElementById('system-events-content');
        
        if (!data.events || data.events.length === 0) {
            container.innerHTML = '<div class="loading">No system events found</div>';
            return;
        }
        
        const table = `
            <table class="audit-table">
                <thead>
                    <tr>
                        <th>Timestamp</th>
                        <th>Event Type</th>
                        <th>Severity</th>
                        <th>Event Name</th>
                        <th>Message</th>
                        <th>Component</th>
                        <th>Memory Usage</th>
                        <th>CPU Usage</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.events.map(event => `
                        <tr>
                            <td class="timestamp">${this.formatTimestamp(event.timestamp)}</td>
                            <td><span class="status-badge status-${event.event_type}">${event.event_type}</span></td>
                            <td><span class="status-badge status-${event.severity_level}">${event.severity_level}</span></td>
                            <td>${event.event_name}</td>
                            <td style="max-width: 300px; overflow: hidden; text-overflow: ellipsis;">${event.event_message}</td>
                            <td>${event.component || '-'}</td>
                            <td>${event.memory_usage_mb ? event.memory_usage_mb.toFixed(1) + '%' : '-'}</td>
                            <td>${event.cpu_usage_percent ? event.cpu_usage_percent.toFixed(1) + '%' : '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${this.renderPagination(data.total, data.offset, data.limit)}
        `;
        
        container.innerHTML = table;
    }
    
    async loadSessions() {
        try {
            const activeOnly = document.getElementById('active-sessions-only')?.checked || false;
            
            const params = new URLSearchParams({
                limit: this.pageSize,
                offset: this.currentPage * this.pageSize,
                active_only: activeOnly
            });
            
            const response = await fetch(`/api/audit/sessions?${params}`);
            const result = await response.json();
            
            if (result.success) {
                this.renderSessions(result.data);
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
            this.showError('Failed to load sessions');
        }
    }
    
    renderSessions(data) {
        const container = document.getElementById('sessions-content');
        
        if (!data.sessions || data.sessions.length === 0) {
            container.innerHTML = '<div class="loading">No sessions found</div>';
            return;
        }
        
        const table = `
            <table class="audit-table">
                <thead>
                    <tr>
                        <th>Session ID</th>
                        <th>IP Address</th>
                        <th>User Agent</th>
                        <th>Created</th>
                        <th>Last Activity</th>
                        <th>Status</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.sessions.map(session => `
                        <tr>
                            <td style="font-family: monospace; font-size: 0.8rem;">${session.session_id.substring(0, 8)}...</td>
                            <td>${session.ip_address}</td>
                            <td style="max-width: 200px; overflow: hidden; text-overflow: ellipsis;">${session.user_agent || '-'}</td>
                            <td class="timestamp">${this.formatTimestamp(session.created_at)}</td>
                            <td class="timestamp">${this.formatTimestamp(session.last_activity)}</td>
                            <td><span class="status-badge ${session.is_active ? 'status-success' : 'status-info'}">${session.is_active ? 'Active' : 'Inactive'}</span></td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
            ${this.renderPagination(data.total, data.offset, data.limit)}
        `;
        
        container.innerHTML = table;
    }
    
    renderPagination(total, offset, limit) {
        const currentPage = Math.floor(offset / limit);
        const totalPages = Math.ceil(total / limit);
        
        if (totalPages <= 1) return '';
        
        return `
            <div class="pagination">
                <button ${currentPage === 0 ? 'disabled' : ''} onclick="auditDashboard.goToPage(${currentPage - 1})">
                    <i class="fas fa-chevron-left"></i> Previous
                </button>
                <span>Page ${currentPage + 1} of ${totalPages} (${total} total)</span>
                <button ${currentPage >= totalPages - 1 ? 'disabled' : ''} onclick="auditDashboard.goToPage(${currentPage + 1})">
                    Next <i class="fas fa-chevron-right"></i>
                </button>
            </div>
        `;
    }
    
    goToPage(page) {
        this.currentPage = page;
        this.loadCurrentTabData();
    }
    
    formatTimestamp(timestamp) {
        return new Date(timestamp).toLocaleString();
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    getStatusClass(status) {
        if (status >= 200 && status < 300) return 'status-success';
        if (status >= 400 && status < 500) return 'status-warning';
        if (status >= 500) return 'status-error';
        return 'status-info';
    }
    
    showError(message) {
        // You can implement a toast notification or modal here
        console.error(message);
    }
    
    async refreshAllData() {
        const refreshButton = document.getElementById('refresh-all');
        const icon = refreshButton.querySelector('i');
        
        icon.classList.add('refresh-indicator');
        refreshButton.disabled = true;
        
        try {
            await this.loadStatistics();
            await this.loadCurrentTabData();
        } finally {
            icon.classList.remove('refresh-indicator');
            refreshButton.disabled = false;
        }
    }
    
    startAutoRefresh() {
        if (this.autoRefreshEnabled) {
            setInterval(() => {
                this.loadStatistics();
            }, this.refreshInterval);
        }
    }
}

// Export data function
async function exportData(table, format) {
    try {
        const url = `/api/audit/export/${format}?table=${table}&limit=10000`;
        window.open(url, '_blank');
    } catch (error) {
        console.error('Failed to export data:', error);
    }
}

// Initialize dashboard when page loads
let auditDashboard;
document.addEventListener('DOMContentLoaded', () => {
    auditDashboard = new AuditDashboard();
});
