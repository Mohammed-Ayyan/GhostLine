"""
Ghostline Microsoft Fluent 2 Dark Stylesheet Builder.
Generates the comprehensive master QSS stylesheet from tokens, providing unified
visual styling across all views, controls, HUD states, menus, and dialogs.
"""

from ghostline.ui.theme.tokens import (
    SURFACE_SIDEBAR, SURFACE_CANVAS, SURFACE_CARD, SURFACE_CARD_HOVER,
    SURFACE_CARD_ACTIVE, SURFACE_ELEVATED, SURFACE_INPUT, SURFACE_INPUT_HOVER,
    SURFACE_CODE, TEXT_PRIMARY, TEXT_SECONDARY, TEXT_TERTIARY, TEXT_QUATERNARY,
    TEXT_DISABLED, STROKE_CONTROL, STROKE_CARD, STROKE_SUBTLE,
    STROKE_FOCUS_OUTER, STROKE_FOCUS_INNER, OVERLAY_HOVER, OVERLAY_PRESSED,
    OVERLAY_SELECTED, BRAND_FILL, BRAND_HOVER, BRAND_PRESSED, BRAND_TEXT,
    BRAND_BADGE_BG, STATUS_SUCCESS_TEXT, STATUS_SUCCESS_BG, STATUS_WARNING_TEXT,
    STATUS_WARNING_BG, STATUS_DANGER_TEXT, STATUS_DANGER_FILL, STATUS_DANGER_HOVER,
    STATUS_DANGER_PRESSED, STATUS_DANGER_BG, RADIUS_CONTROL, RADIUS_CARD,
    RADIUS_DIALOG, FONT_FAMILY_PRIMARY, FONT_FAMILY_CODE
)


def build_fluent_stylesheet() -> str:
    """Builds the master Qt stylesheet conforming to Microsoft Fluent 2 (Dark)."""
    return f"""
/* =========================================================================
   1. Window & Canvas Base
   ========================================================================= */
QMainWindow, QWidget#CentralWidget {{
    background-color: {SURFACE_CANVAS};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 14px;
}}

QDialog, QMessageBox {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 14px;
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_DIALOG}px;
}}

QMessageBox QLabel {{
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QMessageBox QPushButton {{
    background-color: rgba(255, 255, 255, 0.06);
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CONTROL};
    border-radius: {RADIUS_CONTROL}px;
    min-width: 76px;
    height: 28px;
    padding: 4px 16px;
    font-size: 13px;
    font-weight: 500;
}}

QMessageBox QPushButton:hover {{
    background-color: rgba(255, 255, 255, 0.10);
    border-color: #FFFFFF;
}}

QMessageBox QPushButton:pressed {{
    background-color: rgba(255, 255, 255, 0.04);
}}

QMessageBox QPushButton:default {{
    background-color: {BRAND_FILL};
    border-color: {BRAND_FILL};
    color: #FFFFFF;
    font-weight: 600;
}}

QMessageBox QPushButton:default:hover {{
    background-color: {BRAND_HOVER};
    border-color: {BRAND_HOVER};
}}

QMessageBox QPushButton:default:pressed {{
    background-color: {BRAND_PRESSED};
    border-color: {BRAND_PRESSED};
}}

QWidget {{
    outline: none;
}}

/* =========================================================================
   2. Left Navigation Rail (Sidebar)
   ========================================================================= */
QWidget#Sidebar {{
    background-color: {SURFACE_SIDEBAR};
    border-right: 1px solid {STROKE_CARD};
}}

QPushButton#SidebarBtn {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    text-align: left;
    padding: 0px 12px;
    height: 36px;
    border-radius: {RADIUS_CONTROL}px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
    font-weight: 400;
    border: none;
}}

QPushButton#SidebarBtn:hover {{
    background-color: {OVERLAY_HOVER};
    color: {TEXT_PRIMARY};
}}

QPushButton#SidebarBtn:pressed {{
    background-color: {OVERLAY_PRESSED};
    color: {TEXT_PRIMARY};
}}

QPushButton#SidebarBtn:checked, QPushButton#SidebarBtn[active="true"] {{
    background-color: {OVERLAY_SELECTED};
    color: {BRAND_TEXT};
    font-weight: 600;
    border-left: 3px solid {BRAND_FILL};
    padding-left: 9px;
}}

QPushButton#SidebarExitBtn {{
    background-color: transparent;
    color: {STATUS_DANGER_TEXT};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CONTROL}px;
    padding: 0px 12px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
    font-weight: 500;
    height: 34px;
    text-align: left;
}}

QPushButton#SidebarExitBtn:hover {{
    background-color: {STATUS_DANGER_BG};
    border-color: {STATUS_DANGER_TEXT};
    color: #FFFFFF;
}}

QPushButton#SidebarExitBtn:pressed {{
    background-color: {STATUS_DANGER_FILL};
    border-color: {STATUS_DANGER_FILL};
    color: #FFFFFF;
}}

/* =========================================================================
   3. Cards, Settings Rows & Containers
   ========================================================================= */
QFrame#CardFrame {{
    background-color: {SURFACE_CARD};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CARD}px;
}}

QFrame#CardFrame:hover {{
    border-color: {STROKE_CONTROL};
}}

QFrame#IslandFrame {{
    background-color: rgba(28, 28, 28, 0.95);
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_DIALOG}px;
}}

QFrame#SettingsCardRow {{
    background-color: {SURFACE_CARD};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CARD}px;
    min-height: 64px;
}}

QFrame#SettingsCardRow:hover {{
    border-color: {STROKE_CONTROL};
}}

/* =========================================================================
   4. Typography Classes
   ========================================================================= */
QLabel#HeaderTitle {{
    font-size: 26px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
}}

QLabel#SectionTitle {{
    font-size: 15px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
    text-transform: none;
    letter-spacing: 0px;
}}

QLabel#CardTitle {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
}}

QLabel#CardDesc {{
    font-size: 12px;
    font-weight: 400;
    color: {TEXT_SECONDARY};
    font-family: {FONT_FAMILY_PRIMARY};
    line-height: 1.4;
}}

QLabel#BadgeText {{
    font-size: 12px;
    font-weight: 600;
    color: {BRAND_TEXT};
    font-family: {FONT_FAMILY_PRIMARY};
}}

QLabel#BodyStrong {{
    font-size: 14px;
    font-weight: 600;
    color: {TEXT_PRIMARY};
    font-family: {FONT_FAMILY_PRIMARY};
}}

QLabel#Caption {{
    font-size: 12px;
    font-weight: 400;
    color: {TEXT_TERTIARY};
    font-family: {FONT_FAMILY_PRIMARY};
}}

QLabel#CodeText {{
    font-family: {FONT_FAMILY_CODE};
    font-size: 13px;
    color: {TEXT_SECONDARY};
    background-color: {SURFACE_CODE};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CONTROL}px;
    padding: 8px 12px;
}}

/* =========================================================================
   5. Buttons (Primary, Secondary, Subtle, Danger)
   ========================================================================= */
QPushButton {{
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
    font-weight: 500;
    border-radius: {RADIUS_CONTROL}px;
    padding: 6px 14px;
    min-height: 20px;
}}

QPushButton#PrimaryBtn, QPushButton[variant="primary"] {{
    background-color: {BRAND_FILL};
    color: #FFFFFF;
    font-weight: 600;
    border: none;
}}

QPushButton#PrimaryBtn:hover, QPushButton[variant="primary"]:hover {{
    background-color: {BRAND_HOVER};
}}

QPushButton#PrimaryBtn:pressed, QPushButton[variant="primary"]:pressed {{
    background-color: {BRAND_PRESSED};
}}

QPushButton#SecondaryBtn, QPushButton[variant="secondary"] {{
    background-color: {SURFACE_CARD};
    color: {TEXT_PRIMARY};
    font-weight: 500;
    border: 1px solid {STROKE_CONTROL};
}}

QPushButton#SecondaryBtn:hover, QPushButton[variant="secondary"]:hover {{
    background-color: {SURFACE_CARD_HOVER};
    border-color: {TEXT_PRIMARY};
}}

QPushButton#SecondaryBtn:pressed, QPushButton[variant="secondary"]:pressed {{
    background-color: {SURFACE_CARD_ACTIVE};
}}

QPushButton#SubtleBtn, QPushButton[variant="subtle"] {{
    background-color: transparent;
    color: {TEXT_SECONDARY};
    border: none;
}}

QPushButton#SubtleBtn:hover, QPushButton[variant="subtle"]:hover {{
    background-color: {OVERLAY_HOVER};
    color: {TEXT_PRIMARY};
}}

QPushButton#SubtleBtn:pressed, QPushButton[variant="subtle"]:pressed {{
    background-color: {OVERLAY_PRESSED};
}}

QPushButton#WhitePillBtn {{
    background-color: {BRAND_FILL};
    color: #FFFFFF;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 14px;
    border-radius: 14px;
    border: none;
}}

QPushButton#WhitePillBtn:hover {{
    background-color: {BRAND_HOVER};
}}

QPushButton#PillChipBtn {{
    background-color: {SURFACE_CARD};
    color: {TEXT_SECONDARY};
    font-size: 12px;
    font-weight: 500;
    padding: 4px 12px;
    border-radius: 14px;
    border: 1px solid {STROKE_CARD};
}}

QPushButton#PillChipBtn:hover {{
    background-color: {OVERLAY_HOVER};
    color: {TEXT_PRIMARY};
    border-color: {STROKE_CONTROL};
}}

QPushButton#PillChipBtn:checked, QPushButton#PillChipBtn[active="true"] {{
    background-color: {BRAND_BADGE_BG};
    color: {BRAND_TEXT};
    border-color: {BRAND_FILL};
}}

/* =========================================================================
   6. Text Inputs, ComboBoxes & SpinBoxes
   ========================================================================= */
QLineEdit {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CONTROL};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px 10px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
    selection-background-color: {BRAND_FILL};
    selection-color: #FFFFFF;
}}

QLineEdit:hover {{
    background-color: {SURFACE_INPUT_HOVER};
    border-color: {TEXT_SECONDARY};
}}

QLineEdit:focus {{
    border-color: {STROKE_CONTROL};
    border-bottom: 2px solid {BRAND_TEXT};
}}

QComboBox {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CONTROL};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px 10px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
    min-height: 22px;
}}

QComboBox:hover {{
    background-color: {SURFACE_INPUT_HOVER};
    border-color: {TEXT_SECONDARY};
}}

QComboBox:focus {{
    border-bottom: 2px solid {BRAND_TEXT};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: none;
}}

QComboBox QAbstractItemView {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px;
    selection-background-color: {OVERLAY_SELECTED};
    selection-color: #FFFFFF;
}}

QSpinBox {{
    background-color: {SURFACE_INPUT};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CONTROL};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px 8px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 13px;
}}

/* =========================================================================
   7. Sliders (Horizontal Brightness & Volume)
   ========================================================================= */
QSlider::groove:horizontal {{
    height: 4px;
    background: {STROKE_CARD};
    border-radius: 2px;
}}

QSlider::sub-page:horizontal {{
    background: {BRAND_FILL};
    border-radius: 2px;
}}

QSlider::handle:horizontal {{
    background: #FFFFFF;
    border: 2px solid {BRAND_FILL};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background: {BRAND_TEXT};
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}}

/* =========================================================================
   8. Scrollbars (Thin 8px, Low-Contrast, No Arrows)
   ========================================================================= */
QScrollBar:vertical {{
    background: transparent;
    width: 8px;
    margin: 0px;
}}

QScrollBar::handle:vertical {{
    background: #5C5C5C;
    min-height: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical:hover {{
    background: #757575;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
    background: transparent;
}}

QScrollBar:horizontal {{
    background: transparent;
    height: 8px;
    margin: 0px;
}}

QScrollBar::handle:horizontal {{
    background: #5C5C5C;
    min-width: 24px;
    border-radius: 4px;
}}

QScrollBar::handle:horizontal:hover {{
    background: #757575;
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
    background: transparent;
}}

/* =========================================================================
   9. Menus, Dialogs & Tooltips
   ========================================================================= */
QMenu {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CARD}px;
    padding: 4px;
    font-family: {FONT_FAMILY_PRIMARY};
}}

QMenu::item {{
    height: 32px;
    padding: 0 16px;
    border-radius: {RADIUS_CONTROL}px;
    color: {TEXT_PRIMARY};
    font-size: 13px;
}}

QMenu::item:selected {{
    background-color: {OVERLAY_SELECTED};
    color: #FFFFFF;
}}

QMenu::separator {{
    height: 1px;
    background: {STROKE_CARD};
    margin: 4px 8px;
}}

QToolTip {{
    background-color: {SURFACE_ELEVATED};
    color: {TEXT_PRIMARY};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CONTROL}px;
    padding: 4px 8px;
    font-family: {FONT_FAMILY_PRIMARY};
    font-size: 12px;
}}

QProgressBar {{
    background-color: {SURFACE_INPUT};
    border: 1px solid {STROKE_CARD};
    border-radius: {RADIUS_CONTROL}px;
    height: 8px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {BRAND_FILL};
    border-radius: {RADIUS_CONTROL}px;
}}
"""

