/**
 * History Manager for Undo/Redo functionality
 */
class HistoryManager {
    constructor(maxSize = 50) {
        this.undoStack = [];
        this.redoStack = [];
        this.maxSize = maxSize;
    }

    /**
     * Push a new state to the history
     * @param {Object} state - The state object to save
     */
    push(state) {
        // Deep clone state
        const stateClone = this._clone(state);
        
        // Don't push if it's the same as current
        if (this.undoStack.length > 0) {
            const last = this.undoStack[this.undoStack.length - 1];
            if (this._isEqual(last, stateClone)) return;
        }

        this.undoStack.push(stateClone);
        this.redoStack = []; // Clear redo when a new action is performed

        if (this.undoStack.length > this.maxSize) {
            this.undoStack.shift();
        }
    }

    /**
     * Undo to the previous state
     * @returns {Object|null} The previous state or null if no more undo levels
     */
    undo() {
        if (this.undoStack.length <= 1) return null;

        const current = this.undoStack.pop();
        this.redoStack.push(current);

        return this._clone(this.undoStack[this.undoStack.length - 1]);
    }

    /**
     * Redo to the next state
     * @returns {Object|null} The next state or null if no more redo levels
     */
    redo() {
        if (this.redoStack.length === 0) return null;

        const next = this.redoStack.pop();
        this.undoStack.push(next);

        return this._clone(next);
    }

    _clone(obj) {
        return JSON.parse(JSON.stringify(obj));
    }

    _isEqual(a, b) {
        return JSON.stringify(a) === JSON.stringify(b);
    }
}
