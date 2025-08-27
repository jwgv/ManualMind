/**
 * ManualMind Frontend JavaScript
 * Handles API interactions and UI updates
 */

class ManualMindApp {
    constructor() {
        this.apiBase = '/';
        this.init();
    }

    init() {
        this.bindEvents();
        this.checkSystemStatus();
        // Check status every 30 seconds
        setInterval(() => this.checkSystemStatus(), 30000);
    }

    bindEvents() {
        // Query form submission
        document.getElementById('query-form').addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleQuery();
        });

        // Process documents button
        document.getElementById('process-btn').addEventListener('click', () => {
            this.processDocuments();
        });

        // Enter key in textarea (with Ctrl/Cmd)
        document.getElementById('question').addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                e.preventDefault();
                this.handleQuery();
            }
        });

        // Character count and validation
        document.getElementById('question').addEventListener('input', (e) => {
            this.updateCharacterCount();
        });
    }

    async checkSystemStatus() {
        try {
            const response = await fetch(`${this.apiBase}status`);
            const data = await response.json();
            
            const statusDot = document.getElementById('status-dot');
            const systemStatus = document.getElementById('system-status');
            const documentCount = document.getElementById('document-count');

            if (data.status === 'healthy') {
                statusDot.className = 'status-dot healthy';
                systemStatus.textContent = 'Healthy';
                documentCount.textContent = data.processed_documents || 0;
            } else {
                statusDot.className = 'status-dot unhealthy';
                systemStatus.textContent = 'Unhealthy';
                documentCount.textContent = '-';
            }
        } catch (error) {
            console.error('Status check failed:', error);
            document.getElementById('status-dot').className = 'status-dot unhealthy';
            document.getElementById('system-status').textContent = 'Error';
            document.getElementById('document-count').textContent = '-';
        }
    }

    updateCharacterCount() {
        const textarea = document.getElementById('question');
        const charCount = document.getElementById('char-count');
        const charCountContainer = document.querySelector('.character-count');
        
        const currentLength = textarea.value.length;
        const maxLength = 500;
        
        charCount.textContent = currentLength;
        
        // Update styling based on character count
        charCountContainer.className = 'character-count';
        if (currentLength > maxLength * 0.9) { // 90% warning
            charCountContainer.classList.add('warning');
        }
        if (currentLength >= maxLength) { // At limit
            charCountContainer.classList.add('error');
        }
    }

    async handleQuery() {
        const question = document.getElementById('question').value.trim();
        const maxResults = parseInt(document.getElementById('max-results').value);
        
        if (!question) {
            this.showError('Please enter a question.');
            return;
        }
        
        if (question.length > 500) {
            this.showError('Question is too long. Please keep it under 500 characters.');
            return;
        }

        const submitBtn = document.getElementById('submit-btn');
        const loading = document.getElementById('loading');
        
        try {
            // Show loading state
            submitBtn.disabled = true;
            submitBtn.textContent = 'Processing...';
            loading.classList.add('show');
            this.clearError();

            const response = await fetch(`${this.apiBase}query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    question: question,
                    max_results: maxResults
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            this.displayResponse(data);

        } catch (error) {
            console.error('Query failed:', error);
            this.showError(`Failed to process query: ${error.message}`);
        } finally {
            // Reset button state
            submitBtn.disabled = false;
            submitBtn.textContent = 'Ask Question';
            loading.classList.remove('show');
        }
    }

    async processDocuments() {
        const processBtn = document.getElementById('process-btn');
        
        try {
            processBtn.disabled = true;
            processBtn.textContent = 'Processing...';
            this.clearError();

            const response = await fetch(`${this.apiBase}process-documents`, {
                method: 'POST'
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || `HTTP ${response.status}`);
            }

            const data = await response.json();
            this.showSuccess('Document processing started. Check the status indicator for progress.');
            
            // Refresh status after a short delay
            setTimeout(() => this.checkSystemStatus(), 2000);

        } catch (error) {
            console.error('Document processing failed:', error);
            this.showError(`Failed to start document processing: ${error.message}`);
        } finally {
            processBtn.disabled = false;
            processBtn.textContent = 'Process Documents';
        }
    }

    displayResponse(data) {
        const responseSection = document.getElementById('response-section');
        
        const responseCard = document.createElement('div');
        responseCard.className = 'response-card';
        
        responseCard.innerHTML = `
            <div class="query-display">
                <strong>Q:</strong> ${this.escapeHtml(data.query)}
            </div>
            <div class="response-text">
                ${this.formatResponse(data.response)}
            </div>
            <div class="confidence ${data.confidence}">
                Confidence: ${data.confidence.toUpperCase()}
            </div>
            ${this.renderSources(data.sources)}
        `;

        // Insert at the top of response section
        responseSection.insertBefore(responseCard, responseSection.firstChild);
        
        // Scroll to the response
        responseCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    renderSources(sources) {
        if (!sources || sources.length === 0) {
            return '<div class="sources"><h4>Sources</h4><p>No sources available.</p></div>';
        }

        const sourceItems = sources.map(source => `
            <div class="source-item">
                <div class="source-header">
                    <div class="source-name">${this.escapeHtml(source.file_name)}</div>
                    <div class="similarity-score">${(source.similarity_score * 100).toFixed(1)}% match</div>
                </div>
                <div class="source-preview">
                    ${this.escapeHtml(source.preview)}
                </div>
            </div>
        `).join('');

        return `
            <div class="sources">
                <h4>Sources (${sources.length})</h4>
                ${sourceItems}
            </div>
        `;
    }

    formatResponse(response) {
        // Convert line breaks to HTML breaks and preserve formatting
        return this.escapeHtml(response)
            .replace(/\n\n/g, '</p><p>')
            .replace(/\n/g, '<br>')
            .replace(/^/, '<p>')
            .replace(/$/, '</p>');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    showError(message) {
        this.clearError();
        const responseSection = document.getElementById('response-section');
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.id = 'error-message';
        errorDiv.textContent = message;
        responseSection.insertBefore(errorDiv, responseSection.firstChild);
    }

    showSuccess(message) {
        this.clearError();
        const responseSection = document.getElementById('response-section');
        const successDiv = document.createElement('div');
        successDiv.className = 'error';
        successDiv.id = 'success-message';
        successDiv.style.background = '#dcfce7';
        successDiv.style.color = '#166534';
        successDiv.style.borderLeftColor = '#10b981';
        successDiv.textContent = message;
        responseSection.insertBefore(successDiv, responseSection.firstChild);
        
        // Auto-remove success message after 5 seconds
        setTimeout(() => {
            if (document.getElementById('success-message')) {
                document.getElementById('success-message').remove();
            }
        }, 5000);
    }

    clearError() {
        const errorMessage = document.getElementById('error-message');
        const successMessage = document.getElementById('success-message');
        if (errorMessage) errorMessage.remove();
        if (successMessage) successMessage.remove();
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new ManualMindApp();
});