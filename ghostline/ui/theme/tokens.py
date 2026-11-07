"""
Ghostline Microsoft Fluent 2 Dark Design Tokens.
Semantic color tokens, spacing ramps, typography scales, corner radii, and elevations
following the official Microsoft Fluent 2 Design Specification (Dark Theme).
"""

# =============================================================================
# 1. Surfaces & Canvas
# =============================================================================
SURFACE_SIDEBAR = "#141414"        # Left rail navigation background
SURFACE_CANVAS = "#1F1F1F"         # Primary content background
SURFACE_CARD = "#292929"           # Standard settings card / surface
SURFACE_CARD_HOVER = "#333333"     # Interactive surface hover state
SURFACE_CARD_ACTIVE = "#383838"    # Selected / active surface
SURFACE_ELEVATED = "#333333"       # Menus, popouts, dialogs, flyouts
SURFACE_INPUT = "#141414"          # Dark inset text boxes, comboboxes, spinboxes (clearly differentiated from #292929 card)
SURFACE_INPUT_HOVER = "#1E1E1E"    # Input hover fill
SURFACE_CODE = "#1A1A1A"           # Monospace code blocks

# =============================================================================
# 2. Typography & Text Colors (WCAG AA Compliant)
# =============================================================================
TEXT_PRIMARY = "#FFFFFF"           # 16.5:1 contrast against canvas
TEXT_SECONDARY = "#D6D6D6"         # 11.3:1 contrast against canvas
TEXT_TERTIARY = "#ADADAD"          # 7.3:1 contrast against canvas
TEXT_QUATERNARY = "#999999"        # 5.8:1 contrast against canvas
TEXT_DISABLED = "#5C5C5C"          # 2.5:1 disabled text

# =============================================================================
# 3. Strokes & Control Boundaries
# =============================================================================
STROKE_CONTROL = "#858585"         # High-visibility crisp control boundary (4.5:1 against #141414)
TEXT_PLACEHOLDER = "#A0A0A0"       # High-contrast readable placeholder
STROKE_CARD = "#3D3D3D"            # Card border / divider
STROKE_SUBTLE = "rgba(255, 255, 255, 0.08)"
STROKE_FOCUS_OUTER = "#FFFFFF"     # High-contrast 2px focus ring
STROKE_FOCUS_INNER = "#115EA3"     # Brand inner focus accent

# =============================================================================
# 4. Interaction Overlays (Subtle & Transparent Controls)
# =============================================================================
OVERLAY_HOVER = "rgba(255, 255, 255, 0.06)"
OVERLAY_PRESSED = "rgba(255, 255, 255, 0.04)"
OVERLAY_SELECTED = "rgba(255, 255, 255, 0.08)"

# =============================================================================
# 5. Brand Accent (Fluent Blue — Replaces Legacy Cyan)
# =============================================================================
BRAND_FILL = "#115EA3"             # Primary button fill / accent bar
BRAND_HOVER = "#0F6CBD"            # Primary button hover
BRAND_PRESSED = "#0C3B5E"          # Primary button pressed
BRAND_TEXT = "#58A6FF"             # Brand links / accented text (>5.5:1 against #333333)
BRAND_BADGE_BG = "rgba(17, 94, 163, 0.20)"

# =============================================================================
# 6. Status & Feedback
# =============================================================================
STATUS_SUCCESS_TEXT = "#6CCB5F"    # Fluent 2 Green Foreground 1 (>5:1 on #333333)
STATUS_SUCCESS_BG = "rgba(108, 203, 95, 0.15)"
STATUS_WARNING_TEXT = "#FBD161"    # 11.3:1 contrast against canvas
STATUS_WARNING_BG = "rgba(251, 209, 97, 0.15)"
STATUS_DANGER_TEXT = "#FF99A4"     # Fluent 2 Red Foreground 1 (>5.5:1 on #333333)
STATUS_DANGER_FILL = "#C50F1F"     # Danger action fill
STATUS_DANGER_HOVER = "#B20E1C"    # Danger button hover
STATUS_DANGER_PRESSED = "#980C18"  # Danger button pressed
STATUS_DANGER_BG = "rgba(197, 15, 31, 0.15)"

# =============================================================================
# 7. Corner Radii & Geometry
# =============================================================================
RADIUS_CONTROL = 4                 # Buttons, inputs, checkboxes, spinboxes
RADIUS_CARD = 8                    # Settings cards, surface containers
RADIUS_DIALOG = 12                 # Dialogs, overlays, flyouts, HUD
RADIUS_PILL = 9999                 # Fully rounded pills and badges

# =============================================================================
# 8. Standard Heights
# =============================================================================
HEIGHT_CONTROL_DEFAULT = 32        # Standard inputs, combo, buttons
HEIGHT_CONTROL_COMPACT = 24        # Dense tags, badges, chips
HEIGHT_CONTROL_LARGE = 40          # Large primary actions
HEIGHT_NAV_ITEM = 40               # Navigation rail items
HEIGHT_SETTINGS_ROW_MIN = 64       # Windows 11 settings card minimum height

# =============================================================================
# 9. Spacing Ramp (Multiples of 2/4)
# =============================================================================
SPACE_2 = 2
SPACE_4 = 4
SPACE_6 = 6
SPACE_8 = 8
SPACE_10 = 10
SPACE_12 = 12
SPACE_16 = 16
SPACE_20 = 20
SPACE_24 = 24
SPACE_32 = 32
SPACE_40 = 40

# =============================================================================
# 10. Typography Specification
# =============================================================================
FONT_FAMILY_PRIMARY = "'Segoe UI Variable Text', 'Segoe UI', -apple-system, sans-serif"
FONT_FAMILY_CODE = "'Cascadia Mono', Consolas, 'Courier New', monospace"

FONT_SIZE_CAPTION = 12             # 12px, line-height 16px
FONT_SIZE_BODY = 14                # 14px, line-height 20px
FONT_SIZE_SECTION = 16             # 16px semibold, line-height 22px
FONT_SIZE_TITLE = 28               # 28px semibold, line-height 36px

# =============================================================================
# 11. Backward Compatibility Aliases (maps legacy names to Fluent 2 tokens)
# =============================================================================
C_BG_APP = SURFACE_CANVAS
C_BG_SIDEBAR = SURFACE_SIDEBAR
C_BG_CARD = SURFACE_CARD
C_BG_CARD_HOVER = SURFACE_CARD_HOVER
C_BG_CARD_ACTIVE = SURFACE_CARD_ACTIVE
C_BG_CODE = SURFACE_CODE
C_BG_INPUT = SURFACE_INPUT

C_BORDER = STROKE_CARD
C_BORDER_LIGHT = STROKE_CONTROL
C_BORDER_ACCENT = BRAND_FILL

C_CYAN = BRAND_TEXT
C_CYAN_HOVER = BRAND_HOVER
C_EMERALD = STATUS_SUCCESS_TEXT
C_AMBER = STATUS_WARNING_TEXT
C_DANGER = STATUS_DANGER_TEXT
C_GOLD = STATUS_WARNING_TEXT

C_TEXT_PRIMARY = TEXT_PRIMARY
C_TEXT_SECONDARY = TEXT_SECONDARY
C_TEXT_MUTED = TEXT_TERTIARY
C_TEXT_DIM = TEXT_QUATERNARY

