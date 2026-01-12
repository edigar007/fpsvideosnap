/**
 * Tabs Management for Config Assistant
 */
class TabManager {
    constructor() {
        this.tabs = document.querySelectorAll('.tab-btn');
        this.panes = document.querySelectorAll('.tab-pane');
        this.activeTab = 'roi-tab';
        
        this.init();
    }

    init() {
        this.tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const target = tab.getAttribute('data-tab');
                this.switchTab(target);
            });
        });
    }

    switchTab(tabId) {
        // Update UI
        this.tabs.forEach(t => {
            if (t.getAttribute('data-tab') === tabId) {
                t.classList.add('active');
            } else {
                t.classList.remove('active');
            }
        });

        this.panes.forEach(p => {
            if (p.id === 'tab-' + tabId) {
                p.classList.add('active');
            } else {
                p.classList.remove('active');
            }
        });

        this.activeTab = tabId;

        // Dispatch event for other modules
        const event = new CustomEvent('tabChanged', { detail: { tabId } });
        document.dispatchEvent(event);
        
        console.log(`[TabManager] Switched to ${tabId}`);
    }
}

// Global instance
window.tabManager = new TabManager();
