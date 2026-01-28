/**
 * SEO Pocket App
 * Premium UI inspired by Gemini, Claude, NotebookLM, affiliate.fm
 */

class SEOPocketApp {
    constructor() {
        this.api = '/api/analyze';
        this.currentData = null;
        this.botOnlyVisible = false;

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

            // New buttons in search bar
            sourceBtn: document.getElementById('source-btn'),
            shareBtn: document.getElementById('share-btn'),
            botOnlyBtn: document.getElementById('bot-only-btn'),
            botOnlyCount: document.getElementById('bot-only-count'),

            // Preview buttons
            previewSourceBtn: document.getElementById('preview-source-btn'),
            copyBtn: document.getElementById('copy-btn'),

            // Modal
            modalOverlay: document.getElementById('modal-overlay'),
            modalClose: document.getElementById('modal-close'),
            sourceCode: document.getElementById('source-code'),

            // Info chips (affiliate.fm style)
            infoChips: document.getElementById('info-chips'),
            chipGoogleCanonical: document.getElementById('chip-google-canonical'),
            googleCanonicalValue: document.getElementById('google-canonical-value'),
            chipFirstIndexed: document.getElementById('chip-first-indexed'),
            firstIndexedValue: document.getElementById('first-indexed-value'),
            chipLastIndexed: document.getElementById('chip-last-indexed'),
            lastIndexedValue: document.getElementById('last-indexed-value'),
            chipHtmlCanonical: document.getElementById('chip-html-canonical'),
            htmlCanonicalValue: document.getElementById('html-canonical-value'),
            chipHreflang: document.getElementById('chip-hreflang'),
            hreflangValue: document.getElementById('hreflang-value'),
            chipPublished: document.getElementById('chip-published'),
            publishedValue: document.getElementById('published-value'),
            chipHtmlLang: document.getElementById('chip-html-lang'),
            htmlLangValue: document.getElementById('html-lang-value'),
            chipRedirects: document.getElementById('chip-redirects'),
            redirectsValue: document.getElementById('redirects-value'),
            chipFetchTime: document.getElementById('chip-fetch-time'),
            fetchTimeValue: document.getElementById('fetch-time-value'),
            chipStrategy: document.getElementById('chip-strategy'),
            strategyValue: document.getElementById('strategy-value'),

            // Bot Only section
            botOnlySection: document.getElementById('bot-only-section'),
            botOnlyCountHeader: document.getElementById('bot-only-count-header'),
            botOnlyElements: document.getElementById('bot-only-elements'),

            chips: document.querySelectorAll('.quick-actions .chip'),
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

        // Source code button (in search bar)
        this.elements.sourceBtn?.addEventListener('click', () => this.showSourceCode());

        // Preview source button
        this.elements.previewSourceBtn?.addEventListener('click', () => this.showSourceCode());

        // Share button
        this.elements.shareBtn?.addEventListener('click', () => this.shareUrl());

        // Bot Only toggle
        this.elements.botOnlyBtn?.addEventListener('click', () => this.toggleBotOnly());

        // Copy button
        this.elements.copyBtn?.addEventListener('click', () => this.copyToClipboard());

        // Modal
        this.elements.modalClose?.addEventListener('click', () => this.hideModal());
        this.elements.modalOverlay?.addEventListener('click', (e) => {
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
        this.disableActionButtons();

        try {
            const response = await fetch(this.api, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url, include_html: true, detect_cloaking: true }),
            });

            const data = await response.json();

            if (!response.ok) {
                // Handle FastAPI validation errors
                const errorMsg = typeof data.detail === 'string'
                    ? data.detail
                    : (data.detail?.msg || JSON.stringify(data.detail) || 'Failed to analyze URL');
                throw new Error(errorMsg);
            }

            // Handle application-level errors (success: false)
            if (data.success === false) {
                throw new Error(data.error || 'Failed to analyze URL');
            }

            this.currentData = data;
            this.renderResults(data);
            this.enableActionButtons();

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
        // Render new affiliate.fm style info chips
        this.renderInfoChips(data);

        // Render legacy meta tags (for backward compatibility)
        this.renderMetaTags(data);

        // Google indexed data
        this.renderGoogleIndexedData(data);

        // Bot Only section
        this.renderBotOnlySection(data);

        // Live fetch data
        const seoData = data.seo_data || data;
        this.elements.titleCard.textContent = seoData.title || data.title || 'Not found';
        this.elements.h1Card.textContent = seoData.h1 || data.h1 || 'Not found';
        this.elements.descriptionCard.textContent = seoData.description || data.description || 'Not found';

        // Preview iframe - inject base tag and use srcdoc for proper rendering
        const analyzedUrl = data.url;
        if (analyzedUrl && data.html) {
            // Inject base tag into HTML for relative URLs to work
            let htmlWithBase = data.html;
            const baseUrl = data.final_url || analyzedUrl;
            try {
                const urlObj = new URL(baseUrl);
                const baseTag = `<base href="${urlObj.origin}/" target="_blank">`;
                if (htmlWithBase.includes('<head>')) {
                    htmlWithBase = htmlWithBase.replace('<head>', `<head>${baseTag}`);
                } else if (htmlWithBase.includes('<head ')) {
                    htmlWithBase = htmlWithBase.replace(/<head[^>]*>/, `$&${baseTag}`);
                } else if (htmlWithBase.includes('<html')) {
                    htmlWithBase = htmlWithBase.replace(/<html[^>]*>/, `$&<head>${baseTag}</head>`);
                } else {
                    htmlWithBase = `<!DOCTYPE html><html><head>${baseTag}</head><body>` + htmlWithBase + `</body></html>`;
                }
            } catch (e) {
                console.warn('Failed to create base URL:', e);
            }

            // Use srcdoc for inline HTML - allows external resources to load
            this.elements.previewFrame.srcdoc = htmlWithBase;
        }

        // Hreflang
        const hreflang = seoData.hreflang || data.hreflang || [];
        this.renderHreflang(hreflang);

        this.showResults();
    }

    renderInfoChips(data) {
        const seoData = data.seo_data || {};

        // Google Canonical
        const googleCanonical = data.google_canonical;
        if (googleCanonical) {
            this.elements.chipGoogleCanonical.style.display = 'flex';
            // Extract hostname for display
            try {
                const canonicalUrl = new URL(googleCanonical);
                this.elements.googleCanonicalValue.textContent = canonicalUrl.hostname;
                this.elements.googleCanonicalValue.title = googleCanonical;
            } catch {
                this.elements.googleCanonicalValue.textContent = googleCanonical;
            }
        } else {
            this.elements.chipGoogleCanonical.style.display = 'none';
        }

        // First Indexed Date (from Wayback Machine)
        const firstIndexed = data.first_indexed;
        if (firstIndexed) {
            this.elements.chipFirstIndexed.style.display = 'flex';
            this.elements.firstIndexedValue.textContent = firstIndexed;
        } else {
            this.elements.chipFirstIndexed.style.display = 'none';
        }

        // Last Indexed Date (from Wayback Machine)
        const lastIndexed = data.last_indexed;
        if (lastIndexed && this.elements.chipLastIndexed) {
            this.elements.chipLastIndexed.style.display = 'flex';
            this.elements.lastIndexedValue.textContent = lastIndexed;
        } else if (this.elements.chipLastIndexed) {
            this.elements.chipLastIndexed.style.display = 'none';
        }

        // HTML Canonical (from page source)
        const htmlCanonical = seoData.canonical;
        if (htmlCanonical && this.elements.chipHtmlCanonical) {
            this.elements.chipHtmlCanonical.style.display = 'flex';
            try {
                const canonicalUrl = new URL(htmlCanonical);
                this.elements.htmlCanonicalValue.textContent = canonicalUrl.hostname;
                this.elements.htmlCanonicalValue.title = htmlCanonical;
            } catch {
                this.elements.htmlCanonicalValue.textContent = htmlCanonical;
            }
        } else if (this.elements.chipHtmlCanonical) {
            this.elements.chipHtmlCanonical.style.display = 'none';
        }

        // Hreflang languages (summary chip)
        const hreflang = seoData.hreflang || data.hreflang || [];
        if (hreflang.length > 0 && this.elements.chipHreflang) {
            this.elements.chipHreflang.style.display = 'flex';
            // Show language codes
            const langs = hreflang.map(h => h.lang).slice(0, 4).join(', ');
            const suffix = hreflang.length > 4 ? ` +${hreflang.length - 4}` : '';
            this.elements.hreflangValue.textContent = langs + suffix;
            this.elements.hreflangValue.title = hreflang.map(h => `${h.lang}: ${h.url}`).join('\n');
        } else if (this.elements.chipHreflang) {
            this.elements.chipHreflang.style.display = 'none';
        }

        // Published Date
        const published = data.published;
        if (published) {
            this.elements.chipPublished.style.display = 'flex';
            this.elements.publishedValue.textContent = published;
        } else {
            this.elements.chipPublished.style.display = 'none';
        }

        // HTML Lang
        const htmlLang = seoData.html_lang || data.html_lang;
        if (htmlLang) {
            this.elements.chipHtmlLang.style.display = 'flex';
            this.elements.htmlLangValue.textContent = htmlLang;
        } else {
            this.elements.chipHtmlLang.style.display = 'none';
        }

        // Redirects
        const redirects = data.redirects;
        if (redirects && redirects.length > 0) {
            this.elements.chipRedirects.style.display = 'flex';
            // Show redirect chain
            const redirectChain = redirects.join(' -> ');
            this.elements.redirectsValue.textContent = redirectChain;
            this.elements.redirectsValue.title = redirectChain;
        } else if (data.url !== data.final_url && data.final_url) {
            // Show if URL changed (redirect happened)
            this.elements.chipRedirects.style.display = 'flex';
            try {
                const from = new URL(data.url).hostname;
                const to = new URL(data.final_url).hostname;
                if (from !== to) {
                    this.elements.redirectsValue.textContent = `${from} -> ${to}`;
                } else {
                    this.elements.redirectsValue.textContent = 'Redirect detected';
                }
            } catch {
                this.elements.redirectsValue.textContent = 'Redirect detected';
            }
        } else {
            this.elements.chipRedirects.style.display = 'none';
        }

        // Fetch Time
        const fetchTime = data.fetch_time_ms;
        if (fetchTime) {
            this.elements.chipFetchTime.style.display = 'flex';
            this.elements.fetchTimeValue.textContent = `${fetchTime}ms`;
        } else {
            this.elements.chipFetchTime.style.display = 'none';
        }

        // Strategy
        const strategy = data.strategy;
        if (strategy) {
            this.elements.chipStrategy.style.display = 'flex';
            this.elements.strategyValue.textContent = strategy.replace(/_/g, ' ');
        } else {
            this.elements.chipStrategy.style.display = 'none';
        }
    }

    renderBotOnlySection(data) {
        const cloaking = data.cloaking;

        if (cloaking && cloaking.detected && cloaking.bot_only_lines > 0) {
            // Update button badge
            this.elements.botOnlyCount.style.display = 'inline';
            this.elements.botOnlyCount.textContent = cloaking.bot_only_lines;

            // Update header badge
            this.elements.botOnlyCountHeader.textContent = `${cloaking.bot_only_lines} elements`;

            // Render bot-only elements
            const elements = cloaking.bot_only_elements || [];
            if (elements.length > 0) {
                const formattedElements = elements.map(el =>
                    `<span class="bot-line">${this.escapeHtml(el)}</span>`
                ).join('\n');
                this.elements.botOnlyElements.innerHTML = formattedElements;
            } else {
                this.elements.botOnlyElements.textContent = `${cloaking.bot_only_lines} bot-only elements detected`;
            }

            // Show section if toggle is active
            if (this.botOnlyVisible) {
                this.elements.botOnlySection.style.display = 'block';
            }
        } else {
            this.elements.botOnlyCount.style.display = 'none';
            this.elements.botOnlySection.style.display = 'none';
            this.botOnlyVisible = false;
            this.elements.botOnlyBtn?.classList.remove('active');
        }
    }

    toggleBotOnly() {
        this.botOnlyVisible = !this.botOnlyVisible;

        if (this.botOnlyVisible) {
            this.elements.botOnlyBtn?.classList.add('active');
            this.elements.botOnlySection.style.display = 'block';
        } else {
            this.elements.botOnlyBtn?.classList.remove('active');
            this.elements.botOnlySection.style.display = 'none';
        }
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
        const seoData = data.seo_data || {};

        // DataForSEO indexed data (priority - show first)
        if (data.site_indexed) {
            tags.push({ label: 'Google Index', value: 'Indexed', class: 'indexed' });
        }
        if (data.serp_position) {
            tags.push({ label: 'SERP Position', value: `#${data.serp_position}`, class: 'serp-position' });
        }

        // Live canonical (from page)
        const canonical = seoData.canonical || data.canonical;
        if (canonical) {
            tags.push({ label: 'Live Canonical', value: canonical, class: 'canonical' });
        }

        // Robots
        const robots = seoData.robots || data.robots;
        if (robots) {
            tags.push({ label: 'Robots', value: robots, class: 'robots' });
        }

        // Title length
        const title = seoData.title || data.title;
        if (title) {
            tags.push({ label: 'Title', value: `${title.length} chars`, class: 'title' });
        }

        this.elements.metaTags.innerHTML = tags.map(tag => `
            <div class="meta-tag ${tag.class}">
                <span class="meta-tag-label">${tag.label}</span>
                <span class="meta-tag-value" title="${this.escapeHtml(tag.value)}">${this.escapeHtml(tag.value)}</span>
            </div>
        `).join('');
    }

    renderHreflang(hreflang) {
        if (!hreflang || hreflang.length === 0) {
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

    async shareUrl() {
        const currentUrl = window.location.href;

        if (navigator.share) {
            try {
                await navigator.share({
                    title: 'SEO Pocket Analysis',
                    url: currentUrl
                });
            } catch (err) {
                // User cancelled or share failed
                this.copyShareUrl(currentUrl);
            }
        } else {
            this.copyShareUrl(currentUrl);
        }
    }

    async copyShareUrl(url) {
        try {
            await navigator.clipboard.writeText(url);

            const btn = this.elements.shareBtn;
            const originalHTML = btn.innerHTML;
            btn.innerHTML = `
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span class="btn-label">Copied!</span>
            `;
            setTimeout(() => btn.innerHTML = originalHTML, 2000);
        } catch (err) {
            console.error('Copy failed:', err);
        }
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

    enableActionButtons() {
        this.elements.sourceBtn && (this.elements.sourceBtn.disabled = false);
        this.elements.shareBtn && (this.elements.shareBtn.disabled = false);
        this.elements.botOnlyBtn && (this.elements.botOnlyBtn.disabled = false);
    }

    disableActionButtons() {
        this.elements.sourceBtn && (this.elements.sourceBtn.disabled = true);
        this.elements.shareBtn && (this.elements.shareBtn.disabled = true);
        this.elements.botOnlyBtn && (this.elements.botOnlyBtn.disabled = true);
    }

    showResults() {
        this.elements.resultsContainer.classList.add('visible');
    }

    hideResults() {
        this.elements.resultsContainer.classList.remove('visible');
        // Reset bot only section
        this.elements.botOnlySection.style.display = 'none';
        this.botOnlyVisible = false;
        this.elements.botOnlyBtn?.classList.remove('active');
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
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Init
document.addEventListener('DOMContentLoaded', () => {
    window.app = new SEOPocketApp();
});
