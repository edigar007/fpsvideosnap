/**
 * Rules Tab Logic
 * Manages OR-of-AND detection rules configuration.
 * Each rule has: name, enabled, require (list of signals)
 * Valid signals: ocr, template, color, yolo
 */
class RulesTab {
    constructor() {
        this.rulesList = document.getElementById('rules-list');
        this.addRuleBtn = document.getElementById('add-rule-btn');
        this.saveBtn = document.getElementById('save-rules-btn');
        
        // Internal state: array of rule objects
        this.rules = [];
        this.selectedRuleName = null;
        
        // Valid signal types
        this.validSignals = ['ocr', 'template', 'color', 'yolo'];
        this.signalLabels = {
            'ocr': 'OCR 文字匹配',
            'template': '模板匹配',
            'color': '颜色检测',
            'yolo': 'YOLO 检测'
        };
        
        this.init();
    }

    init() {
        if (this.addRuleBtn) {
            this.addRuleBtn.addEventListener('click', () => this.addNewRule());
        }
        
        if (this.saveBtn) {
            this.saveBtn.addEventListener('click', () => this.saveRules());
        }
        
        // Listen for tab changes
        document.addEventListener('tabChanged', (e) => {
            if (e.detail.tabId === 'rules') {
                this.render();
            }
        });
    }

    /**
     * Set rules from loaded config
     */
    setRules(rules) {
        this.rules = Array.isArray(rules) ? [...rules] : [];
        this.render();
    }

    /**
     * Add a new empty rule
     */
    addNewRule() {
        const ruleNum = this.rules.length + 1;
        const newRule = {
            name: `rule_${ruleNum}`,
            enabled: true,
            require: ['color']  // Default to color as it's the most common
        };
        this.rules.push(newRule);
        this.render();
        
        // Scroll to the new rule
        setTimeout(() => {
            const items = this.rulesList.querySelectorAll('.rule-item');
            if (items.length > 0) {
                items[items.length - 1].scrollIntoView({ behavior: 'smooth' });
            }
        }, 100);
    }

    /**
     * Remove a rule by index
     */
    removeRule(index) {
        if (confirm(`确定删除规则 "${this.rules[index].name}"？`)) {
            this.rules.splice(index, 1);
            this.render();
        }
    }

    selectRule(ruleName) {
        this.selectedRuleName = ruleName;
        if (window.app && window.app.setCurrentRule) {
            window.app.setCurrentRule(ruleName);
        }
        this.render(); // Re-render to show selection
    }

    deselectRule() {
        this.selectedRuleName = null;
        if (window.app && window.app.setCurrentRule) {
            window.app.setCurrentRule(null);
        }
        this.render();
    }

    /**
     * Render the rules list
     */
    render() {
        if (!this.rulesList) return;
        
        this.rulesList.innerHTML = '';

        // Add "Edit Global" button at top if there are rules
        if (this.rules.length > 0) {
            const globalBtn = document.createElement('div');
            globalBtn.className = `rule-item global-config-item ${!this.selectedRuleName ? 'selected' : ''}`;
            globalBtn.innerHTML = `
                <div class="rule-header" style="cursor: pointer;">
                    <div class="rule-name-row">
                        <i class="fas fa-globe"></i> 
                        <span style="font-weight: bold; margin-left: 8px;">全局默认配置</span>
                        ${!this.selectedRuleName ? '<span class="status-badge" style="margin-left: auto;">当前编辑</span>' : ''}
                    </div>
                </div>
            `;
            globalBtn.onclick = () => this.deselectRule();
            this.rulesList.appendChild(globalBtn);
        }
        
        if (this.rules.length === 0) {
            this.rulesList.innerHTML = '<div class="empty-state">尚未配置规则，将使用默认加权计算</div>';
            return;
        }
        
        this.rules.forEach((rule, index) => {
            const item = document.createElement('div');
            item.className = `rule-item ${this.selectedRuleName === rule.name ? 'selected' : ''}`;
            item.dataset.index = index;
            
            item.innerHTML = `
                <div class="rule-header">
                    <div class="rule-name-row">
                        <div class="rule-select-area" style="flex: 1; display: flex; align-items: center; cursor: pointer;">
                            <input type="text" class="rule-name-input" value="${this.escapeHtml(rule.name)}" 
                                   placeholder="规则名称" title="规则名称" onclick="event.stopPropagation()">
                            ${this.selectedRuleName === rule.name ? '<span class="status-badge" style="margin-left: 10px;">当前编辑</span>' : ''}
                        </div>
                        <label class="toggle small">
                            <input type="checkbox" class="rule-enabled" ${rule.enabled ? 'checked' : ''}>
                            <span class="slider"></span>
                        </label>
                        <button class="btn-icon delete-rule" title="删除规则">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
                <div class="rule-signals">
                    <label>条件 (AND):</label>
                    <div class="signal-checkboxes">
                        ${this.validSignals.map(sig => `
                            <label class="signal-checkbox">
                                <input type="checkbox" data-signal="${sig}" 
                                       ${rule.require.includes(sig) ? 'checked' : ''}>
                                <span>${this.signalLabels[sig]}</span>
                            </label>
                        `).join('')}
                    </div>
                </div>
            `;
            
            // Event listeners
            const selectArea = item.querySelector('.rule-select-area');
            selectArea.addEventListener('click', () => this.selectRule(rule.name));

            const nameInput = item.querySelector('.rule-name-input');
            nameInput.addEventListener('change', (e) => {
                const oldName = this.rules[index].name;
                const newName = e.target.value.trim() || `rule_${index + 1}`;
                this.rules[index].name = newName;
                if (this.selectedRuleName === oldName) {
                    this.selectRule(newName); // Update selection if renamed
                }
            });
            
            const enabledCheck = item.querySelector('.rule-enabled');
            enabledCheck.addEventListener('change', (e) => {
                this.rules[index].enabled = e.target.checked;
            });
            
            const deleteBtn = item.querySelector('.delete-rule');
            deleteBtn.addEventListener('click', () => this.removeRule(index));
            
            const signalChecks = item.querySelectorAll('.signal-checkbox input');
            signalChecks.forEach(check => {
                check.addEventListener('change', () => {
                    this.updateRuleSignals(index, item);
                });
            });
            
            this.rulesList.appendChild(item);
        });
    }

    /**
     * Update the require array for a rule based on checkboxes
     */
    updateRuleSignals(index, item) {
        const checks = item.querySelectorAll('.signal-checkbox input:checked');
        const signals = Array.from(checks).map(c => c.dataset.signal);
        this.rules[index].require = signals;
    }

    /**
     * Validate rules before saving
     */
    validate() {
        const errors = [];
        const seenNames = new Set();
        
        this.rules.forEach((rule, i) => {
            // Check name
            if (!rule.name || !rule.name.trim()) {
                errors.push(`规则 ${i + 1}: 名称不能为空`);
            } else if (seenNames.has(rule.name)) {
                errors.push(`规则 ${i + 1}: 名称 "${rule.name}" 重复`);
            } else {
                seenNames.add(rule.name);
            }
            
            // Check require
            if (!rule.require || rule.require.length === 0) {
                errors.push(`规则 "${rule.name}": 至少需要一个条件`);
            }
        });
        
        return errors;
    }

    /**
     * Save rules to backend
     */
    async saveRules() {
        const game = document.getElementById('game-selector').value;
        if (!game) {
            alert('请先选择游戏');
            return;
        }
        
        // Client-side validation
        const errors = this.validate();
        if (errors.length > 0) {
            alert('配置错误:\n' + errors.join('\n'));
            return;
        }
        
        try {
            const response = await fetch(`/api/config/${game}/rules`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ rules: this.rules })
            });
            
            if (response.ok) {
                const data = await response.json();
                if (window.app && window.app.showStatus) {
                    window.app.showStatus('规则配置已保存', 'success');
                } else {
                    alert('规则配置已保存');
                }
                
                // Update config preview
                if (window.configPreview && data.config) {
                    window.configPreview.update(data.config);
                }
            } else {
                const errorData = await response.json();
                alert(`保存失败: ${errorData.error || '未知错误'}`);
            }
        } catch (err) {
            console.error('Save Rules Error:', err);
            alert('网络错误');
        }
    }

    /**
     * HTML escape helper
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.rulesTab = new RulesTab();
});
