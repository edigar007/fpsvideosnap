# Learnings - KillDetector OR-of-AND Rules

## Completed: 2026-01-22
## Status: ALL TASKS COMPLETE

---

## Task 4 Implementation

### Key Design Decisions
1. **Rules mode vs Legacy mode**: 
   - `rules: []` (empty) or missing → Legacy weighted scoring
   - `rules` has items but all disabled → Rules mode with no matches (is_kill=False)
   - `rules` has enabled items → Evaluate OR-of-AND logic

2. **Signal Boolean Conversion**:
   - `ocr`: True if signals['ocr'] > 0
   - `yolo`: True if signals['yolo'] > 0
   - `color`: True if cached_color_pct >= self.color_threshold
   - `template`: True if max_score >= per-template threshold (default 0.8)

3. **Confidence Output**:
   - Rules mode hit → confidence = 1.0
   - Rules mode miss → confidence = 0.0
   - Legacy mode → weighted confidence (0.0 to 1.0)

### Code Changes
- Added `self.rules` in `__init__` to store rules from config
- Added `_get_signal_booleans()` method to convert signal values to booleans
- Added `_evaluate_rules()` method to implement OR-of-AND logic
- Modified `process_frame()` to use rules mode when applicable
- Modified `_process_candidates_sequential()` for batch processing support

### Testing Insights
1. **conftest.py had cv2 mocked** - This broke real OpenCV operations. Removed cv2 from mock list.
2. **YOLO mock needed batch support** - Mock must return one result per frame in batch.
3. **Template matching behavior** - OpenCV template matching gives 1.0 for exact matches regardless of color differences if structure is same. Need structurally different patterns to test threshold failures.

### File References
- `src/ai/kill_detector.py:127-215` - New helper methods
- `src/ai/kill_detector.py:306-347` - Modified process_frame
- `src/ai/kill_detector.py:349-411` - Modified batch processing
- `tests/test_ai.py:320-813` - New test classes and fixtures

---

## Task 5-6: Config Assistant Implementation

### API Endpoints Added
- `GET /api/config/<game>/rules` → Returns `{"rules": [...]}`
- `PUT /api/config/<game>/rules` → Updates rules, returns full config

### Frontend Components
- `src/tools/config_assistant/static/js/tab-rules.js` - New RulesTab class
- Rules tab in index.html with button and pane
- CSS styles for rule items and signal checkboxes

### Validation
- Backend validation mirrors ConfigLoader constraints
- Client-side validation before save (duplicate names, empty require)

---

## Task 7: Documentation

### Files Updated
- `config/default_game_template.yaml` - Added `detection.rules: []` with example comments
- `CONFIG.md` - Added comprehensive Section 2.4 for detection rules

---

## Final Test Results

| Test Suite | Result |
|------------|--------|
| AI tests (test_ai.py) | 24/24 passed |
| Config tests (test_config.py) | 11/11 passed |
| Rules API tests (TestRulesAPI) | 15/15 passed |
| **Total Core Tests** | **50/50 passed** |

### Rules Mode Specific Tests
- test_rules_hit_single_rule_yolo_and_color ✓
- test_rules_hit_multiple_rules_or ✓
- test_rules_miss_no_rule_satisfied ✓
- test_rules_disabled_rule_ignored ✓
- test_legacy_fallback_when_rules_empty ✓
- test_legacy_fallback_when_rules_missing ✓
- test_template_threshold_from_config ✓
- test_template_passes_with_default_threshold ✓
- test_batch_rules_mode_confidence_1_0 ✓
- test_batch_legacy_mode_weighted_confidence ✓
- test_batch_rules_mode_no_events_when_no_match ✓
