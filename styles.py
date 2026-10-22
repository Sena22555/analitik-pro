# -*- coding: utf-8 -*-
"""
Дизайн-система Analitik Pro.

Все цвета интерфейса и графиков описаны токенами (LIGHT / DARK),
таблица стилей Qt собирается из одного шаблона для обеих тем,
поэтому светлая и тёмная тема всегда согласованы.
"""
import os
from string import Template

LIGHT = {
    'page': '#f4f4f1',
    'surface': '#fcfcfb',
    'surface2': '#f0efec',
    'hover': '#e8e7e2',
    'input': '#ffffff',
    'border': '#e4e3dd',
    'border_strong': '#d3d2ca',
    'grid': '#efeee9',
    'row_alt': '#f8f8f6',
    'text': '#161615',
    'text2': '#52514e',
    'muted': '#898781',
    'disabled': '#b5b3ab',
    'accent': '#2a78d6',
    'accent_hover': '#256abf',
    'accent_pressed': '#1c5cab',
    'on_accent': '#ffffff',
    'accent_soft': '#e6f0fb',
    'accent_text': '#1c5cab',
    'good': '#006300',
    'warning': '#9a6700',
    'critical': '#d03b3b',
    'scroll': '#d3d2ca',
    'scroll_hover': '#b5b3ab',
    'tooltip_bg': '#161615',
    'tooltip_text': '#f0efec',
}

DARK = {
    'page': '#0f0f0e',
    'surface': '#1a1a19',
    'surface2': '#242422',
    'hover': '#2e2e2c',
    'input': '#141413',
    'border': '#2c2c2a',
    'border_strong': '#3a3a37',
    'grid': '#252523',
    'row_alt': '#1e1e1d',
    'text': '#f0efec',
    'text2': '#c3c2b7',
    'muted': '#898781',
    'disabled': '#5a5955',
    'accent': '#3987e5',
    'accent_hover': '#5598e7',
    'accent_pressed': '#2a78d6',
    'on_accent': '#ffffff',
    'accent_soft': '#1b2a3f',
    'accent_text': '#86b6ef',
    'good': '#0ca30c',
    'warning': '#fab219',
    'critical': '#e66767',
    'scroll': '#3a3a37',
    'scroll_hover': '#52514e',
    'tooltip_bg': '#f0efec',
    'tooltip_text': '#161615',
}


def tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


_QSS = Template("""
* { outline: none; }

QWidget {
    color: $text;
    font-size: 13px;
}
QMainWindow, QDialog, QWidget#Page {
    background: $page;
}
QToolTip {
    background: $tooltip_bg;
    color: $tooltip_text;
    border: none;
    padding: 6px 8px;
    border-radius: 6px;
}

/* ---------- Шапка ---------- */
QWidget#Header {
    background: $surface;
    border-bottom: 1px solid $border;
}
QLabel#AppTitle { font-size: 15px; font-weight: 600; }
QLabel#AppSubtitle { font-size: 12px; color: $muted; }

QFrame#Segmented {
    background: $surface2;
    border-radius: 9px;
}
QPushButton#SegButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 5px 16px;
    color: $text2;
    font-weight: 500;
}
QPushButton#SegButton:hover { color: $text; }
QPushButton#SegButton:checked {
    background: $surface;
    border: 1px solid $border;
    color: $text;
    font-weight: 600;
}

/* ---------- Кнопки ---------- */
QPushButton, QToolButton {
    background: $surface;
    color: $text;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 6px 14px;
    font-weight: 500;
}
QPushButton:hover, QToolButton:hover { background: $surface2; }
QPushButton:pressed, QToolButton:pressed { background: $hover; }
QPushButton:disabled, QToolButton:disabled {
    color: $disabled;
    border-color: $border;
    background: $surface;
}
QToolButton::menu-indicator {
    image: url("$icons/chevron-down-$mode.svg");
    subcontrol-position: right center;
    subcontrol-origin: padding;
    width: 10px;
    right: 8px;
}
QToolButton { padding-right: 26px; }

QPushButton[variant="primary"] {
    background: $accent;
    color: $on_accent;
    border: 1px solid $accent;
    font-weight: 600;
}
QPushButton[variant="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[variant="primary"]:pressed { background: $accent_pressed; border-color: $accent_pressed; }
QPushButton[variant="primary"]:disabled {
    background: $surface2;
    color: $disabled;
    border-color: $border;
}

QPushButton[variant="ghost"] {
    background: transparent;
    border: 1px solid transparent;
    color: $text2;
}
QPushButton[variant="ghost"]:hover { background: $surface2; color: $text; }
QPushButton[variant="ghost"]:disabled { color: $disabled; background: transparent; }

QPushButton[variant="chip"] {
    background: $surface;
    border: 1px solid $border;
    border-radius: 12px;
    padding: 3px 12px;
    min-height: 18px;
    max-height: 18px;
    color: $text2;
}
QPushButton[variant="chip"]:hover {
    background: $accent_soft;
    border-color: $accent;
    color: $accent_text;
}
QPushButton[variant="chip"]:disabled { color: $disabled; background: $surface; border-color: $border; }

QPushButton[variant="icon"] {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 8px;
    padding: 0;
    min-width: 32px; max-width: 32px;
    min-height: 32px; max-height: 32px;
    font-size: 16px;
    color: $text2;
}
QPushButton[variant="icon"]:hover { background: $surface2; color: $text; }

/* ---------- Поля ввода ---------- */
QLineEdit, QComboBox, QSpinBox {
    background: $input;
    border: 1px solid $border_strong;
    border-radius: 8px;
    padding: 5px 10px;
    min-height: 20px;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover { border-color: $muted; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border-color: $accent; }
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {
    color: $disabled;
    border-color: $border;
    background: $surface;
}

QComboBox { padding-right: 28px; }
QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: 26px;
    border: none;
}
QComboBox::down-arrow {
    image: url("$icons/chevron-down-$mode.svg");
    width: 12px;
    height: 12px;
}
QComboBox QAbstractItemView {
    background: $surface;
    border: 1px solid $border;
    border-radius: 8px;
    padding: 4px;
    selection-background-color: $accent_soft;
    selection-color: $text;
    outline: none;
}

QSpinBox { padding-right: 24px; }
QSpinBox::up-button, QSpinBox::down-button {
    subcontrol-origin: border;
    width: 22px;
    border: none;
    background: transparent;
}
QSpinBox::up-button { subcontrol-position: top right; margin-top: 2px; }
QSpinBox::down-button { subcontrol-position: bottom right; margin-bottom: 2px; }
QSpinBox::up-arrow { image: url("$icons/chevron-up-$mode.svg"); width: 10px; height: 10px; }
QSpinBox::down-arrow { image: url("$icons/chevron-down-$mode.svg"); width: 10px; height: 10px; }

QPlainTextEdit, QTextEdit {
    background: $input;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 8px;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QPlainTextEdit:focus { border-color: $accent; }
QPlainTextEdit#SqlEditor {
    font-family: "Menlo", "SF Mono", "Consolas", "DejaVu Sans Mono", monospace;
    font-size: 13px;
    padding: 10px 12px;
}
QTextEdit#Flat, QTextBrowser#Flat {
    background: transparent;
    border: none;
    padding: 0;
}

QCheckBox { spacing: 10px; padding: 3px 0; }
QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid $border_strong;
    border-radius: 5px;
    background: $input;
}
QCheckBox::indicator:hover { border-color: $accent; }
QCheckBox::indicator:checked {
    background: $accent;
    border-color: $accent;
    image: url("$icons/check.svg");
}

/* ---------- Карточки ---------- */
QFrame#Card {
    background: $surface;
    border: 1px solid $border;
    border-radius: 12px;
}
QFrame#DropZone {
    background: $surface;
    border: 2px dashed $border_strong;
    border-radius: 18px;
}
QFrame#DropZone[active="true"] {
    background: $accent_soft;
    border-color: $accent;
}
QLabel#HeroTitle { font-size: 26px; font-weight: 700; }
QLabel#HeroText { font-size: 14px; color: $text2; }
QLabel#HeroBadge {
    background: $accent_soft;
    color: $accent_text;
    border-radius: 10px;
    padding: 3px 10px;
    font-size: 12px;
    font-weight: 600;
}
QLabel#CardTitle { font-size: 13px; font-weight: 600; }
QLabel#Hint { font-size: 12px; color: $muted; }
QLabel#FieldLabel { font-size: 12px; color: $text2; font-weight: 500; }
QLabel#SectionLabel {
    font-size: 11px;
    color: $muted;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#StatLabel { font-size: 12px; color: $muted; }
QLabel#StatValue { font-size: 24px; font-weight: 600; }
QLabel#StatNote { font-size: 12px; color: $text2; }
QLabel#EmptyTitle { font-size: 16px; font-weight: 600; color: $text2; }

/* ---------- Таблицы ---------- */
QTableView {
    background: $surface;
    alternate-background-color: $row_alt;
    border: none;
    gridline-color: $grid;
    selection-background-color: $accent_soft;
    selection-color: $text;
}
QHeaderView { background: $surface; }
QHeaderView::section {
    background: $surface;
    color: $text2;
    border: none;
    border-bottom: 1px solid $border;
    border-right: 1px solid $grid;
    padding: 7px 10px;
    font-weight: 600;
}
QHeaderView::section:vertical {
    color: $muted;
    font-weight: 400;
    border-right: 1px solid $border;
    border-bottom: 1px solid $grid;
    padding: 0 8px;
}
QTableCornerButton::section {
    background: $surface;
    border: none;
    border-bottom: 1px solid $border;
    border-right: 1px solid $border;
}

/* ---------- Прокрутка и разделители ---------- */
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 32px; }
QScrollBar::handle:horizontal { background: $scroll; border-radius: 3px; min-width: 32px; }
QScrollBar::handle:hover { background: $scroll_hover; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QScrollBar::add-page, QScrollBar::sub-page { background: transparent; }

QSplitter::handle { background: transparent; }
QSplitter::handle:horizontal { width: 12px; }
QSplitter::handle:vertical { height: 12px; }

QProgressBar {
    background: $surface2;
    border: none;
    border-radius: 3px;
    max-height: 6px;
    min-height: 6px;
}
QProgressBar::chunk { background: $accent; border-radius: 3px; }

/* ---------- Меню и статус ---------- */
QMenuBar { background: $surface; border-bottom: 1px solid $border; padding: 2px 6px; }
QMenuBar::item { background: transparent; padding: 5px 10px; border-radius: 6px; }
QMenuBar::item:selected { background: $surface2; }
QMenu {
    background: $surface;
    border: 1px solid $border;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item { padding: 7px 28px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background: $accent_soft; color: $text; }
QMenu::item:disabled { color: $disabled; }
QMenu::separator { height: 1px; background: $border; margin: 5px 8px; }

QStatusBar {
    background: $surface;
    border-top: 1px solid $border;
    color: $muted;
    font-size: 12px;
}
QStatusBar::item { border: none; }
QStatusBar QLabel { color: $muted; font-size: 12px; padding: 0 8px; }

/* ---------- Вкладки в диалогах ---------- */
QTabWidget::pane { border: none; }
QTabBar::tab {
    background: transparent;
    color: $text2;
    padding: 8px 14px;
    border: none;
    border-bottom: 2px solid transparent;
}
QTabBar::tab:hover { color: $text; }
QTabBar::tab:selected { color: $text; border-bottom: 2px solid $accent; font-weight: 600; }

QMessageBox QLabel { color: $text; }
QDialogButtonBox QPushButton { min-width: 84px; }
""")


def build_stylesheet(dark: bool, icons_dir: str) -> str:
    """Собирает таблицу стилей Qt для выбранной темы."""
    values = dict(tokens(dark))
    values['mode'] = 'dark' if dark else 'light'
    values['icons'] = os.path.abspath(icons_dir).replace('\\', '/')
    return _QSS.substitute(values)
