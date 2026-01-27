/**
 * SEO Pocket App
 * Premium UI inspired by Gemini, Claude, NotebookLM
 */

class SEOPocketApp {
    constructor() {
        this.api = '/api/analyze';
        this.currentData = null;

        this.elements = {
            urlInput: document.getElementById('url-input'),
            analyzeBtn: document.getElementById('analyze-btn'),
            btnText: document.getElementById('btn-text'),
            btnSpinner: document.getElementById('btn-spinner'),
            resultsContainer: document.getElementById('results'),
            errorContainer: document.getElementById('error-container'),
            errorText: document.getElementById('error-text'),
            metaTags: document.getElementById('meta-tags'),
            titleCard: document.getElementById('title-content'),
            h1Card: document.getElementById('h1-content'),
            descriptionCard: document.getElementById('description-content'),
            previewFrame: document.getElementById('preview-frame'),
            hreflangBody: document.getElementById('hreflang-body'),
            hreflangCard: document.getElementById('hreflang-card'),
            indexedSection: document.getElementById('google-indexed-section'),
            indexedTitleContent: document.getElementById('indexed-title-content'),
            indexedDescriptionContent: document.getElementById('indexed-description-content'),
            sourceBtn: document.getElementById('source-btn'),
            copyBtn: document.getElementById('copy-btn'),
            modalOverlay: document.getElementById('modal-overlay'),
            modalClose: document.getElementById('modal-close'),
            sourceCode: document.getElementById('source-code'),
            chips: document.querySelectorAll('.chip'),
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.elements.urlInput.focus();

        // Check URL params
        const params = new URLSearchParams(window.location.search);
        const urlParam = params.get('url');
        if (urlParam) {
            this.elements.urlInput.value = urlParam;
            this.analyze();
        }
    }

    bindEvents() {
        // Analyze button
        this.elements.analyzeBtn.addEventListener('click', () => this.analyze());

        // Enter key
        this.elements.urlInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.analyze();
        });

        // Quick action chips
        this.elements.chips.forEach(chip => {
            chip.addEventListener('click', () => {
                const url = chip.dataset.url;
                if (url) {
                    this.elements.urlInput.value = url;
                    this.analyze();
                }
            });
        });

        // Source code button
        this.elements.sourceBtn.addEventListener('click', () => this.showSourceCode());

        // Copy button
        this.elements.copyBtn.addEventListener('click', () => this.copyToClipboard());

        // Modal
        this.elements.modalClose.addEventListener('click', () => this.hideModal());
        this.elements.modalOverlay.addEventListener('click', (e) => {
            if (e.target === this.elements.modalOverlay) this.hideModal();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.hideModal();
        });
    }

    async analyze() {
        let url = this.elements.urlInput.value.trim();

        if (!url) {
            this.showError('Please enter a URL');
            return;
        }

        // Add protocol
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            url = 'https://' + url;
            this.elements.urlInput.value = url;
        }

        // Validate
        try {
            new URL(url);
        } catch {
            this.showError('Invalid URL format');
            return;
        }

        this.setLoading(true);
        this.hideError();
        this.hideResults();

        try {
            const response = await fetch(this.api, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url }),
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || 'Failed to analyze URL');
            }

            this.currentData = data;
            this.renderResults(data);

            // Update URL
            const newUrl = new URL(window.location);
            newUrl.searchParams.set('url', url);
            window.history.pushState({}, '', newUrl);

        } catch (error) {
            console.error('Analysis error:', error);
            this.showError(error.message || 'Failed to analyze URL');
        } finally {
            this.setLoading(false);
        }
    }

    renderResults(data) {
        this.renderMetaTags(data);

        // Google indexed data
        this.renderGoogleIndexedData(data);

        // Live fetch data
        this.elements.titleCard.textContent = data.title || 'Not found';
        this.elements.h1Card.textContent = data.h1 || 'Not found';
        this.elements.descriptionCard.textContent = data.description || 'Not found';

        if (data.html) {
            // Add base tag to resolve relative URLs (images, CSS, etc.)
            let htmlWithBase = data.html;
            const baseUrl = data.url || data.canonical;
            if (baseUrl) {
                // Extract origin from URL
                try {
                    const urlObj = new URL(baseUrl);
                    const baseTag = `<base href="${urlObj.origin}/">`;
                    // Insert base tag after <head> or at beginning
                    if (htmlWithBase.includes('<head>')) {
                        htmlWithBase = htmlWithBase.replace('<head>', `<head>${baseTag}`);
                    } else if (htmlWithBase.includes('<head ')) {
                        htmlWithBase = htmlWithBase.replace(/<head[^>]*>/, `$&${baseTag}`);
                    } else {
                        htmlWithBase = baseTag + htmlWithBase;
                    }
                } catch (e) {
                    console.warn('Failed to create base URL:', e);
                }
            }
            const blob = new Blob([htmlWithBase], { type: 'text/html' });
            this.elements.previewFrame.src = URL.createObjectURL(blob);
        }

        this.renderHreflang(data.hreflang || []);
        this.showResults();
    }

    renderGoogleIndexedData(data) {
        const indexedSection = document.getElementById('google-indexed-section');
        const indexedTitleContent = document.getElementById('indexed-title-content');
        const indexedDescriptionContent = document.getElementById('indexed-description-content');

        if (!indexedSection) return;

        const hasIndexedData = data.indexed_title || data.indexed_description || data.site_indexed;

        if (hasIndexedData) {
            indexedSection.classList.add('visible');
            if (indexedTitleContent) {
                indexedTitleContent.textContent = data.indexed_title || 'Not found in index';
            }
            if (indexedDescriptionContent) {
                indexedDescriptionContent.textContent = data.indexed_description || 'Not found in index';
            }
        } else {
            indexedSection.classList.remove('visible');
        }
    }

    renderMetaTags(data) {
        const tags = [];

        // DataForSEO indexed data (priority - show first)
        if (data.site_indexed) {
            tags.push({ label: 'Google Index', value: '✓ Indexed', class: 'indexed' });
        }
        if (data.serp_position) {
            tags.push({ label: 'SERP Position', value: `#${data.serp_position}`, class: 'serp-position' });
        }

        // Google indexed canonical (from DataForSEO - what Google actually sees)
        if (data.google_canonical) {
            tags.push({ label: 'Google Canonical', value: data.google_canonical, class: 'google-canonical' });
        }

        // Live fetch data
        if (data.html_lang) {
            tags.push({ label: 'Lang', value: data.html_lang, class: 'lang' });
        }
        if (data.canonical) {
            tags.push({ label: 'Live Canonical', value: data.canonical, class: 'canonical' });
        }
        if (data.robots) {
            tags.push({ label: 'Robots', value: data.robots, class: 'robots' });
        }
        if (data.title) {
            tags.push({ label: 'Title', value: `${data.title.length} chars`, class: 'title' });
        }
        if (data.fetch_time_ms) {
            tags.push({ label: 'Time', value: `${data.fetch_time_ms}ms`, class: '' });
        }

        this.elements.metaTags.innerHTML = tags.map(tag => `
            <div class="meta-tag ${tag.class}">
                <span class="meta-tag-label">${tag.label}</span>
                <span class="meta-tag-value" title="${this.escapeHtml(tag.value)}">${this.escapeHtml(tag.value)}</span>
            </div>
        `).join('');
    }

    renderHreflang(hreflang) {
        if (hreflang.length === 0) {
            this.elements.hreflangCard.classList.remove('visible');
            return;
        }

        this.elements.hreflangCard.classList.add('visible');
        this.elements.hreflangBody.innerHTML = hreflang.map(item => `
            <tr>
                <td><span class="lang-badge">${this.escapeHtml(item.lang)}</span></td>
                <td>${this.escapeHtml(item.href)}</td>
            </tr>
        `).join('');
    }

    showSourceCode() {
        if (!this.currentData?.html) return;

        const formatted = this.formatHtml(this.currentData.html);
        this.elements.sourceCode.textContent = formatted;
        this.showModal();
    }

    formatHtml(html) {
        return html
            .replace(/></g, '>\n<')
            .split('\n')
            .map(line => line.trim())
            .filter(line => line.length > 0)
            .join('\n');
    }

    async copyToClipboard() {
        if (!this.currentData?.html) return;

        try {
            await navigator.clipboard.writeText(this.currentData.html);

            const btn = this.elements.copyBtn;
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                Copied!
            `;
            setTimeout(() => btn.innerHTML = originalHTML, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
    }

    setLoading(loading) {
        this.elements.analyzeBtn.disabled = loading;
        this.elements.btnText.style.display = loading ? 'none' : 'flex';
        this.elements.btnSpinner.style.display = loading ? 'block' : 'none';
    }

    showResults() {
        this.elements.resultsContainer.classList.add('visible');
    }

    hideResults() {
        this.elements.resultsContainer.classList.remove('visible');
    }

    showError(message) {
        this.elements.errorText.textContent = message;
        this.elements.errorContainer.classList.add('visible');
    }

    hideError() {
        this.elements.errorContainer.classList.remove('visible');
    }

    showModal() {
        this.elements.modalOverlay.classList.add('visible');
        document.body.style.overflow = 'hidden';
    }

    hideModal() {
        this.elements.modalOverlay.classList.remove('visible');
        document.body.style.overflow = '';
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    window.app = new SEOPocketApp();
});
