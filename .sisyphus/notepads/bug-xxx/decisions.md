# Decisions: bug-xxx

## 2026-01-21 Session

### Decision: Use DOMRect ratio instead of this.scale

**Context**: Need to convert mouse client coordinates to canvas pixel coordinates.

**Options considered**:
1. Keep `/ this.scale` approach but fix scale synchronization
2. Use `offsetX/offsetY` from mouse event directly
3. Use DOMRect `width/height` to calculate actual scale ratio

**Decision**: Option 3 - DOMRect ratio calculation

**Rationale**:
- `getBoundingClientRect()` returns the **actual rendered size** including all CSS transforms
- This is more robust than relying on `this.scale` which is a JS variable that could desync
- Works correctly regardless of:
  - CSS constraints like `max-width: 100%`
  - Browser zoom (Ctrl+/-)
  - Device pixel ratio (high DPI displays)
  - Any other CSS transforms

**Trade-offs**:
- Slightly more complex calculation
- But self-correcting and doesn't rely on state synchronization

### Decision: Skip pytest enhancement (Task 5)

**Context**: Plan included optional task to add pytest regression tests for ROI precision.

**Decision**: SKIP

**Rationale**:
- `tests/test_config_assistant_api.py` has pre-existing issues:
  - Imports non-existent symbols (`CONFIG_GAMES_DIR`, `TEMPLATE_ROOT`)
  - References outdated API endpoints
- Adding new tests requires first fixing existing test infrastructure
- This is out of scope for the bug fix
- The bug is frontend-only (JS coordinate math) - backend API is unchanged

### Decision: Mark Task 4 as blocked (not skipped)

**Context**: Task 4 requires manual UI verification which cannot be automated.

**Decision**: Mark as BLOCKED, not skipped or completed

**Rationale**:
- The verification is essential to confirm the fix works
- Cannot be performed by AI (requires browser interaction)
- User must complete this verification before the bug can be considered fixed
- Marking as "completed" without verification would be dishonest
