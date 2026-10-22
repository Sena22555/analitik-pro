import json
import os
import sqlite3
import sys
import warnings
from pathlib import Path

import pandas as pd
from PySide6.QtCore import Qt, QAbstractTableModel, QThread, Signal, QSettings, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QShortcut, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFileDialog, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar, QPushButton, QScrollArea,
    QSizePolicy, QSpinBox, QSplitter, QStackedWidget, QTabWidget, QTableView, QTextEdit, QToolButton,
    QVBoxLayout, QWidget
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas

from analytics import (
    apply_chart_theme, category_columns, create_data_profile_report, detect_outliers, generate_insights,
    generate_report, load_file as backend_load_file, looks_like_date, numeric_columns, numeric_summary, plot_bar_chart,
    plot_boxplot, plot_correlation, plot_density, plot_distribution_comparison, plot_heatmap,
    plot_histograms, plot_line, plot_missing_matrix, plot_outliers, plot_pie_chart, plot_scatter,
    plot_time_series, quality_score, strongest_correlations
)
from styles import build_stylesheet, tokens

APP_NAME = 'Analitik Pro'
APP_VERSION = '3.0'
SUPPORTED_SUFFIXES = ('.csv', '.xlsx', '.xls')


def resource_path(relative_path):
    """Путь к ресурсу: работает и при запуске из исходников, и в собранном приложении."""
    base_path = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


ICONS_DIR = resource_path(os.path.join('assets', 'icons'))

# при сужении окна matplotlib предупреждает, что не может ужать подписи, — это не ошибка
warnings.filterwarnings('ignore', message='Tight layout not applied')


def plural(n, forms):
    """plural(5, ('строка', 'строки', 'строк')) -> '5 строк'"""
    n10, n100 = abs(n) % 10, abs(n) % 100
    form = forms[0] if n10 == 1 and n100 != 11 else forms[1] if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else forms[2]
    return f'{n:,} {form}'.replace(',', ' ')


ROWS = ('строка', 'строки', 'строк')
COLS = ('колонка', 'колонки', 'колонок')

VISUALIZATIONS = [
    ('Распределения', [
        ('hist', 'Гистограмма'),
        ('density', 'Плотность распределения'),
        ('box', 'Диаграмма размаха'),
        ('outliers', 'Выбросы'),
        ('distribution_comparison', 'Сравнение распределений'),
    ]),
    ('Связи', [
        ('corr', 'Матрица корреляций'),
        ('scatter', 'Точечная диаграмма'),
        ('heatmap', 'Тепловая карта'),
    ]),
    ('Категории', [
        ('bar', 'Самые частые значения'),
        ('pie', 'Доли (кольцевая)'),
    ]),
    ('Динамика и качество', [
        ('line', 'Значения по строкам'),
        ('time_series', 'Временной ряд'),
        ('missing', 'Карта пропусков'),
    ]),
]


# ============================================================
# Вспомогательные виджеты
# ============================================================

def make_button(text, variant=None, tooltip=None, slot=None):
    button = QPushButton(text)
    if variant:
        button.setProperty('variant', variant)
    if tooltip:
        button.setToolTip(tooltip)
    if slot:
        button.clicked.connect(slot)
    button.setCursor(Qt.PointingHandCursor)
    return button


def make_label(text, name=None, wrap=False):
    label = QLabel(text)
    if name:
        label.setObjectName(name)
    label.setWordWrap(wrap)
    return label


def make_card():
    card = QFrame()
    card.setObjectName('Card')
    return card


def card_header(title, hint=None):
    """Строка заголовка карточки: название, подсказка и место под кнопки справа."""
    row = QHBoxLayout()
    row.setSpacing(10)
    row.addWidget(make_label(title, 'CardTitle'))
    hint_label = make_label(hint or '', 'Hint')
    row.addWidget(hint_label)
    row.addStretch()
    return row, hint_label


def repolish(widget):
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Worker(QThread):
    finished = Signal(object)
    error = Signal(str)

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs

    def run(self):
        try:
            result = self.fn(*self.args, **self.kwargs)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


class PandasModel(QAbstractTableModel):
    data_modified = Signal()

    def __init__(self, df=pd.DataFrame(), editable=True, right_aligned=None):
        super().__init__()
        self._df = df.copy()
        self._editable = editable
        self._right_aligned = set(right_aligned or [])

    def update(self, df):
        self.beginResetModel()
        self._df = df.copy()
        self.endResetModel()

    def rowCount(self, parent=None):
        return len(self._df.index)

    def columnCount(self, parent=None):
        return len(self._df.columns)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role in (Qt.DisplayRole, Qt.EditRole):
            value = self._df.iat[index.row(), index.column()]
            if pd.isna(value):
                return ""
            if role == Qt.DisplayRole and isinstance(value, float):
                return f'{value:g}' if abs(value) < 1e15 else str(value)
            return str(value)
        if role == Qt.TextAlignmentRole:
            if (pd.api.types.is_numeric_dtype(self._df.dtypes.iloc[index.column()])
                    or self._df.columns[index.column()] in self._right_aligned):
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def flags(self, index):
        if not index.isValid():
            return Qt.ItemIsEnabled
        flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        return flags | Qt.ItemIsEditable if self._editable else flags

    def setData(self, index, value, role=Qt.EditRole):
        if index.isValid() and role == Qt.EditRole:
            try:
                col_name = self._df.columns[index.column()]
                if value == "":
                    val_to_set = pd.NA
                else:
                    dtype = self._df[col_name].dtype
                    if pd.api.types.is_bool_dtype(dtype):
                        val_to_set = str(value).lower() in ('true', '1', 't', 'y', 'yes', 'да')
                    elif pd.api.types.is_integer_dtype(dtype):
                        val_to_set = int(value)
                    elif pd.api.types.is_float_dtype(dtype):
                        val_to_set = float(str(value).replace(',', '.'))
                    else:
                        val_to_set = value
                self._df.iat[index.row(), index.column()] = val_to_set
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
                self.data_modified.emit()
                return True
            except Exception as e:
                print(f"Ошибка ввода данных: {e}")
                return False
        return False

    def sort(self, column, order):
        self.layoutAboutToBeChanged.emit()
        col_name = self._df.columns[column]
        self._df.sort_values(by=col_name, ascending=(order == Qt.AscendingOrder), inplace=True, ignore_index=True)
        self.layoutChanged.emit()

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return str(self._df.columns[section])
        return str(section + 1)

    def dataframe(self):
        return self._df


class StatTile(QFrame):
    """Карточка с ключевой цифрой."""

    def __init__(self, title):
        super().__init__()
        self.setObjectName('Card')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(2)
        layout.addWidget(make_label(title, 'StatLabel'))
        self.value = make_label('—', 'StatValue')
        layout.addWidget(self.value)
        self.note = make_label('', 'StatNote')
        layout.addWidget(self.note)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

    def set(self, value, note='', color=None):
        self.value.setText(value)
        self.note.setText(note)
        self.value.setStyleSheet(f'color: {color};' if color else '')


def configure_table(table, editable=True):
    table.setAlternatingRowColors(True)
    table.setSelectionBehavior(QAbstractItemView.SelectRows if editable else QAbstractItemView.SelectItems)
    table.setShowGrid(False)
    table.setWordWrap(False)
    table.verticalHeader().setDefaultSectionSize(30)
    table.verticalHeader().setMinimumWidth(36)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    table.horizontalHeader().setHighlightSections(False)
    table.horizontalHeader().setMinimumSectionSize(70)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollPerPixel)
    table.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)


# ============================================================
# Главное окно
# ============================================================

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(QIcon(resource_path(os.path.join('assets', 'icon.png'))))
        self.setAcceptDrops(True)
        self.df = pd.DataFrame()
        self.display_df = self.df
        self.conn = None
        self.current_file = None
        self.selected_visualizations = ['hist', 'corr', 'scatter', 'bar', 'pie', 'box']
        self.detached_windows = []
        self._insights = {}
        self._correlations = []

        self.settings = QSettings('AnalitikApp', 'Settings')
        self.load_settings()

        self.init_ui()
        self.create_menu_bar()
        self.create_status_bar()
        self.create_shortcuts()
        self.apply_theme()
        self.set_ui_enabled(False)

    # ---------- настройки ----------

    def load_settings(self):
        """Загружает тему и геометрию окна. По умолчанию тема берётся из системы."""
        system_dark = False
        try:
            system_dark = QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Dark
        except AttributeError:
            pass
        self.dark_theme = self.settings.value('dark_theme', system_dark, type=bool)
        geometry = self.settings.value('geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(1360, 860)

    def save_settings(self):
        self.settings.setValue('dark_theme', self.dark_theme)
        self.settings.setValue('geometry', self.saveGeometry())

    # ---------- меню, статус, горячие клавиши ----------

    def create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu('Файл')
        open_action = QAction('Открыть файл…', self)
        open_action.setShortcut('Ctrl+O')
        open_action.triggered.connect(self.load_file)
        file_menu.addAction(open_action)
        file_menu.addAction('Открыть демо-данные', self.load_demo)

        save_action = QAction('Сохранить данные…', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_data)
        file_menu.addAction(save_action)

        file_menu.addSeparator()
        export_menu = file_menu.addMenu('Экспорт')
        export_menu.addAction('Отчёт…', self.export_report)
        export_menu.addAction('Графики…', self.save_plots)

        file_menu.addSeparator()
        exit_action = QAction('Выход', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        view_menu = menubar.addMenu('Вид')
        self.theme_action = QAction('Тёмная тема', self)
        self.theme_action.setCheckable(True)
        self.theme_action.setChecked(self.dark_theme)
        self.theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(self.theme_action)
        view_menu.addSeparator()
        view_menu.addAction('Открепить таблицу', self.detach_table)

        analysis_menu = menubar.addMenu('Анализ')
        summary_action = QAction('Обновить сводку', self)
        summary_action.setShortcut('Ctrl+I')
        summary_action.triggered.connect(self.show_summary)
        analysis_menu.addAction(summary_action)

        plots_action = QAction('Построить графики', self)
        plots_action.setShortcut('Ctrl+G')
        plots_action.triggered.connect(self.generate_plots)
        analysis_menu.addAction(plots_action)

        analysis_menu.addSeparator()
        analysis_menu.addAction('Анализ выбросов…', self.analyze_outliers)
        analysis_menu.addAction('Корреляционный анализ', self.show_correlation_analysis)

        help_menu = menubar.addMenu('Помощь')
        help_menu.addAction('Горячие клавиши', self.show_shortcuts)
        help_menu.addAction('О программе', self.show_about)

    def create_status_bar(self):
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('Готов к работе')
        self.data_label = QLabel('Нет данных')
        self.status_bar.addPermanentWidget(self.data_label)

    def create_shortcuts(self):
        for key in ('Ctrl+Return', 'Ctrl+Enter'):
            shortcut = QShortcut(QKeySequence(key), self.sql_input)
            shortcut.setContext(Qt.WidgetShortcut)
            shortcut.activated.connect(self.run_sql)
        for i in range(3):
            shortcut = QShortcut(QKeySequence(f'Ctrl+{i + 1}'), self)
            shortcut.activated.connect(lambda i=i: self.tabs.setCurrentIndex(i))

    # ---------- тема ----------

    def toggle_theme(self):
        self.dark_theme = not self.dark_theme
        self.apply_theme()
        self.save_settings()
        if self.plot_layout.count() > 0 and not self.display_df.empty:
            self.generate_plots()

    def apply_theme(self):
        mode = 'dark' if self.dark_theme else 'light'
        QApplication.instance().setStyleSheet(build_stylesheet(self.dark_theme, ICONS_DIR))
        apply_chart_theme(self.dark_theme)
        self.theme_action.setChecked(self.dark_theme)
        icon = 'sun' if self.dark_theme else 'moon'
        self.theme_btn.setIcon(QIcon(os.path.join(ICONS_DIR, f'{icon}-{mode}.svg')))
        self.theme_btn.setToolTip('Светлая тема' if self.dark_theme else 'Тёмная тема')
        self.render_insights()
        if not self.df.empty:
            self.update_data_info()

    # ---------- построение интерфейса ----------

    def init_ui(self):
        central = QWidget()
        central.setObjectName('Page')
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.build_header())

        self.tabs = QTabWidget()
        self.tabs.tabBar().hide()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self.build_data_tab(), 'Данные')
        self.tabs.addTab(self.build_visualization_tab(), 'Графики')
        self.tabs.addTab(self.build_sql_tab(), 'SQL')
        self.tabs.currentChanged.connect(self.on_tab_changed)
        layout.addWidget(self.tabs)
        self.setCentralWidget(central)

    def build_header(self):
        header = QWidget()
        header.setObjectName('Header')
        header.setAttribute(Qt.WA_StyledBackground, True)
        row = QHBoxLayout(header)
        row.setContentsMargins(18, 10, 18, 10)
        row.setSpacing(12)

        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(QPixmap(resource_path(os.path.join('assets', 'icon.png'))).scaled(
            30, 30, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        brand.addWidget(logo)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(make_label(APP_NAME, 'AppTitle'))
        self.subtitle = make_label('Анализ и визуализация данных', 'AppSubtitle')
        titles.addWidget(self.subtitle)
        brand.addLayout(titles)
        brand.addStretch()
        left = QWidget()
        left.setLayout(brand)
        brand.setContentsMargins(0, 0, 0, 0)

        segmented = QFrame()
        segmented.setObjectName('Segmented')
        seg_layout = QHBoxLayout(segmented)
        seg_layout.setContentsMargins(3, 3, 3, 3)
        seg_layout.setSpacing(2)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for index, name in enumerate(['Данные', 'Графики', 'SQL']):
            button = QPushButton(name)
            button.setObjectName('SegButton')
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setToolTip(f'Ctrl+{index + 1}')
            self.nav_group.addButton(button, index)
            seg_layout.addWidget(button)
        self.nav_group.button(0).setChecked(True)
        self.nav_group.idClicked.connect(lambda i: self.tabs.setCurrentIndex(i))

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(8)
        actions.addStretch()
        self.header_demo_btn = make_button('Демо-данные', 'ghost', 'Открыть пример набора данных', self.load_demo)
        self.load_btn = make_button('Открыть файл', 'primary', 'CSV или Excel · Ctrl+O', self.load_file)
        self.theme_btn = make_button('', 'icon', slot=self.toggle_theme)
        self.theme_btn.setIconSize(QSize(18, 18))
        actions.addWidget(self.header_demo_btn)
        actions.addWidget(self.load_btn)
        actions.addWidget(self.theme_btn)
        right = QWidget()
        right.setLayout(actions)

        row.addWidget(left, 1)
        row.addWidget(segmented, 0, Qt.AlignCenter)
        row.addWidget(right, 1)
        return header

    # ----- вкладка «Данные» -----

    def build_data_tab(self):
        self.data_stack = QStackedWidget()
        self.data_stack.addWidget(self.build_empty_state())
        self.data_stack.addWidget(self.build_workspace())
        return self.data_stack

    def build_empty_state(self):
        page = QWidget()
        page.setObjectName('Page')
        outer = QVBoxLayout(page)
        outer.setContentsMargins(40, 32, 40, 32)
        outer.addStretch(1)

        self.drop_zone = QFrame()
        self.drop_zone.setObjectName('DropZone')
        self.drop_zone.setMaximumWidth(820)
        zone = QVBoxLayout(self.drop_zone)
        zone.setContentsMargins(48, 40, 48, 40)
        zone.setSpacing(14)
        zone.setAlignment(Qt.AlignHCenter)

        icon = QLabel()
        icon.setPixmap(QPixmap(resource_path(os.path.join('assets', 'icon.png'))).scaled(
            72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        icon.setAlignment(Qt.AlignCenter)
        zone.addWidget(icon)

        badge = make_label('CSV · XLSX', 'HeroBadge')
        badge.setAlignment(Qt.AlignCenter)
        zone.addWidget(badge, 0, Qt.AlignCenter)

        title = make_label('Загрузите данные для анализа', 'HeroTitle')
        title.setAlignment(Qt.AlignCenter)
        zone.addWidget(title)

        text = make_label('Перетащите файл в окно или выберите его на диске. Analitik Pro посчитает '
                          'статистику, найдёт пропуски, дубликаты и выбросы и построит графики.', 'HeroText', wrap=True)
        text.setAlignment(Qt.AlignCenter)
        zone.addWidget(text)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch()
        buttons.addWidget(make_button('Выбрать файл', 'primary', 'Ctrl+O', self.load_file))
        buttons.addWidget(make_button('Открыть демо-данные', None, '364 сотрудника: зарплаты, отделы, города',
                                      self.load_demo))
        buttons.addStretch()
        zone.addSpacing(6)
        zone.addLayout(buttons)

        features = QHBoxLayout()
        features.setSpacing(12)
        for name, hint in [('Профиль данных', 'пропуски, дубли, качество'),
                           ('13 видов графиков', 'светлая и тёмная тема'),
                           ('SQL по таблице', 'запросы к вашим данным')]:
            card = make_card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(2)
            card_layout.addWidget(make_label(name, 'CardTitle'))
            card_layout.addWidget(make_label(hint, 'Hint'))
            features.addWidget(card, 1)
        zone.addSpacing(10)
        zone.addLayout(features)

        outer.addWidget(self.drop_zone, 0, Qt.AlignHCenter)
        outer.addStretch(1)
        return page

    def build_workspace(self):
        page = QWidget()
        page.setObjectName('Page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # Ключевые цифры
        tiles = QHBoxLayout()
        tiles.setSpacing(12)
        self.tile_rows = StatTile('Строки')
        self.tile_cols = StatTile('Колонки')
        self.tile_missing = StatTile('Пропуски')
        self.tile_dupes = StatTile('Дубликаты')
        self.tile_quality = StatTile('Качество данных')
        for tile in (self.tile_rows, self.tile_cols, self.tile_missing, self.tile_dupes, self.tile_quality):
            tiles.addWidget(tile)
        layout.addLayout(tiles)

        # Поиск, сортировка, экспорт
        toolbar = make_card()
        bar = QHBoxLayout(toolbar)
        bar.setContentsMargins(12, 10, 12, 10)
        bar.setSpacing(8)

        self.filter_column_select = QComboBox()
        self.filter_column_select.setToolTip('Колонка для поиска')
        self.filter_column_select.setMinimumWidth(150)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText('Поиск по выбранной колонке…')
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.returnPressed.connect(self.apply_filter)
        self.apply_filter_btn = make_button('Найти', None, 'Показать строки, где колонка содержит текст',
                                            self.apply_filter)

        self.sort_column_select = QComboBox()
        self.sort_column_select.setToolTip('Колонка для сортировки')
        self.sort_column_select.setMinimumWidth(150)
        self.sort_order_select = QComboBox()
        self.sort_order_select.addItems(['По возрастанию', 'По убыванию'])
        self.sort_btn = make_button('Сортировать', None, None, self.sort_data)

        self.detach_btn = make_button('Открепить', 'ghost', 'Открыть таблицу в отдельном окне', self.detach_table)
        self.export_btn = QToolButton()
        self.export_btn.setText('Экспорт')
        self.export_btn.setPopupMode(QToolButton.InstantPopup)
        self.export_btn.setCursor(Qt.PointingHandCursor)
        export_menu = QMenu(self.export_btn)
        export_menu.addAction('Сохранить данные (CSV / Excel)…', self.save_data)
        export_menu.addAction('Отчёт в папку…', self.export_report)
        export_menu.addAction('Графики в PNG…', self.save_plots)
        self.export_btn.setMenu(export_menu)

        bar.addWidget(self.filter_column_select)
        bar.addWidget(self.filter_input, 1)
        bar.addWidget(self.apply_filter_btn)
        bar.addSpacing(12)
        bar.addWidget(self.sort_column_select)
        bar.addWidget(self.sort_order_select)
        bar.addWidget(self.sort_btn)
        bar.addSpacing(12)
        bar.addWidget(self.detach_btn)
        bar.addWidget(self.export_btn)
        layout.addWidget(toolbar)

        # Таблица и статистика слева, инсайты справа
        table_card = make_card()
        table_layout = QVBoxLayout(table_card)
        table_layout.setContentsMargins(14, 12, 14, 6)
        table_layout.setSpacing(10)
        header, self.table_hint = card_header('Таблица')
        self.show_nulls_btn = make_button('Пропуски', 'chip', 'Строки с пустыми значениями', self.show_null_rows)
        self.show_duplicates_btn = make_button('Дубликаты', 'chip', 'Повторяющиеся строки', self.show_duplicate_rows)
        self.show_outliers_btn = make_button('Выбросы', 'chip', 'Строки со значениями за 1,5 IQR', self.show_outlier_rows)
        self.reset_view_btn = make_button('Сбросить', 'ghost', 'Показать все строки', self.reset_view)
        for button in (self.show_nulls_btn, self.show_duplicates_btn, self.show_outliers_btn, self.reset_view_btn):
            header.addWidget(button)
        table_layout.addLayout(header)

        self.table = QTableView()
        configure_table(self.table)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.model = PandasModel(self.display_df)
        self.model.data_modified.connect(self.sync_sql)
        self.table.setModel(self.model)
        table_layout.addWidget(self.table)

        stats_card = make_card()
        stats_layout = QVBoxLayout(stats_card)
        stats_layout.setContentsMargins(14, 12, 14, 6)
        stats_layout.setSpacing(10)
        stats_header, self.stats_hint = card_header('Статистика', 'числовые колонки')
        stats_layout.addLayout(stats_header)
        self.stats_table = QTableView()
        configure_table(self.stats_table, editable=False)
        self.stats_table.verticalHeader().hide()
        self.stats_model = PandasModel(editable=False)
        self.stats_table.setModel(self.stats_model)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        stats_layout.addWidget(self.stats_table)

        left = QSplitter(Qt.Vertical)
        left.addWidget(table_card)
        left.addWidget(stats_card)
        left.setStretchFactor(0, 3)
        left.setStretchFactor(1, 1)
        left.setSizes([480, 200])

        insights_card = make_card()
        insights_layout = QVBoxLayout(insights_card)
        insights_layout.setContentsMargins(16, 12, 16, 12)
        insights_layout.setSpacing(10)
        insights_header, _ = card_header('Инсайты')
        self.summary_btn = make_button('Обновить', 'ghost', 'Пересчитать по текущей выборке · Ctrl+I', self.show_summary)
        insights_header.addWidget(self.summary_btn)
        insights_layout.addLayout(insights_header)
        self.summary_text = QTextEdit()
        self.summary_text.setObjectName('Flat')
        self.summary_text.setReadOnly(True)
        insights_layout.addWidget(self.summary_text)

        main = QSplitter(Qt.Horizontal)
        main.addWidget(left)
        main.addWidget(insights_card)
        main.setStretchFactor(0, 1)
        main.setSizes([960, 340])
        layout.addWidget(main, 1)
        return page

    # ----- вкладка «Графики» -----

    def build_visualization_tab(self):
        page = QWidget()
        page.setObjectName('Page')
        layout = QHBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        panel = make_card()
        panel.setFixedWidth(300)
        controls = QVBoxLayout(panel)
        controls.setContentsMargins(16, 14, 16, 16)
        controls.setSpacing(6)

        def section(title):
            controls.addSpacing(8)
            controls.addWidget(make_label(title.upper(), 'SectionLabel'))

        def field(title, combo):
            controls.addWidget(make_label(title, 'FieldLabel'))
            controls.addWidget(combo)

        controls.addWidget(make_label('Настройка графиков', 'CardTitle'))
        self.visuals_hint = make_label('', 'Hint', wrap=True)
        controls.addWidget(self.visuals_hint)
        self.choose_visuals_btn = make_button('Выбрать графики…', None, 'Какие графики строить', self.open_visual_selection)
        controls.addWidget(self.choose_visuals_btn)

        grid_row = QHBoxLayout()
        grid_row.addWidget(make_label('Графиков в ряд', 'FieldLabel'))
        grid_row.addStretch()
        self.columns_spin = QSpinBox()
        self.columns_spin.setRange(1, 4)
        self.columns_spin.setValue(2)
        self.columns_spin.setFixedWidth(72)
        grid_row.addWidget(self.columns_spin)
        controls.addSpacing(4)
        controls.addLayout(grid_row)

        self.metric_select = QComboBox()
        self.date_select = QComboBox()
        self.scatter_x_select = QComboBox()
        self.scatter_y_select = QComboBox()
        self.scatter_color_select = QComboBox()
        self.category_select = QComboBox()
        self.category2_select = QComboBox()

        section('Показатель')
        field('Числовая колонка', self.metric_select)
        field('Дата для временного ряда', self.date_select)
        section('Точечная диаграмма')
        field('Ось X', self.scatter_x_select)
        field('Ось Y', self.scatter_y_select)
        field('Цвет по группе', self.scatter_color_select)
        section('Категории')
        field('Категория (столбцы, доли)', self.category_select)
        field('Вторая категория (тепловая карта)', self.category2_select)

        controls.addStretch()
        self.plot_progress = QProgressBar()
        self.plot_progress.setRange(0, 0)
        self.plot_progress.setTextVisible(False)
        self.plot_progress.setVisible(False)
        controls.addWidget(self.plot_progress)
        self.generate_plots_btn = make_button('Построить графики', 'primary', 'Ctrl+G', self.generate_plots)
        controls.addWidget(self.generate_plots_btn)
        self.update_visuals_hint()

        self.plot_container = QWidget()
        self.plot_layout = QGridLayout(self.plot_container)
        self.plot_layout.setContentsMargins(0, 0, 4, 0)
        self.plot_layout.setAlignment(Qt.AlignTop)
        self.plot_layout.setHorizontalSpacing(14)
        self.plot_layout.setVerticalSpacing(14)

        self.plot_scroll = QScrollArea()
        self.plot_scroll.setWidgetResizable(True)
        self.plot_scroll.setFrameShape(QFrame.NoFrame)
        self.plot_scroll.setWidget(self.plot_container)

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.addStretch()
        title = make_label('Здесь появятся графики', 'EmptyTitle')
        title.setAlignment(Qt.AlignCenter)
        hint = make_label('Загрузите данные, выберите графики слева и нажмите «Построить графики».', 'Hint', wrap=True)
        hint.setAlignment(Qt.AlignCenter)
        empty_layout.addWidget(title)
        empty_layout.addWidget(hint)
        empty_layout.addStretch()

        self.plot_stack = QStackedWidget()
        self.plot_stack.addWidget(empty)
        self.plot_stack.addWidget(self.plot_scroll)

        layout.addWidget(panel)
        layout.addWidget(self.plot_stack, 1)
        return page

    # ----- вкладка «SQL» -----

    def build_sql_tab(self):
        page = QWidget()
        page.setObjectName('Page')
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)

        editor_card = make_card()
        editor_layout = QVBoxLayout(editor_card)
        editor_layout.setContentsMargins(14, 12, 14, 14)
        editor_layout.setSpacing(10)
        header, _ = card_header('SQL-запрос', 'таблица называется data · Ctrl+Enter — выполнить')
        self.sql_templates_btn = make_button('Шаблоны', 'ghost', 'Вставить готовый запрос', self.show_sql_templates)
        self.clear_sql_btn = make_button('Очистить', 'ghost', None, lambda: self.sql_input.clear())
        self.sql_run_btn = make_button('Выполнить', 'primary', 'Ctrl+Enter', self.run_sql)
        for button in (self.sql_templates_btn, self.clear_sql_btn, self.sql_run_btn):
            header.addWidget(button)
        editor_layout.addLayout(header)

        self.sql_input = QPlainTextEdit('SELECT * FROM data LIMIT 10;')
        self.sql_input.setObjectName('SqlEditor')
        self.sql_input.setPlaceholderText('Введите SQL-запрос…')
        self.sql_input.setTabStopDistance(32)
        editor_layout.addWidget(self.sql_input)

        result_card = make_card()
        result_layout = QVBoxLayout(result_card)
        result_layout.setContentsMargins(14, 12, 14, 6)
        result_layout.setSpacing(10)
        result_header, self.sql_hint = card_header('Результат', 'запрос ещё не выполнялся')
        result_layout.addLayout(result_header)
        self.sql_result = QTableView()
        configure_table(self.sql_result, editable=False)
        result_layout.addWidget(self.sql_result)

        self.sql_splitter = QSplitter(Qt.Vertical)
        self.sql_splitter.addWidget(editor_card)
        self.sql_splitter.addWidget(result_card)
        self.sql_splitter.setSizes([240, 520])
        layout.addWidget(self.sql_splitter)
        return page

    # ---------- общее ----------

    def on_tab_changed(self, index):
        button = self.nav_group.button(index)
        if button and not button.isChecked():
            button.setChecked(True)

    def set_ui_enabled(self, enabled: bool):
        controls = [
            self.summary_btn, self.export_btn, self.detach_btn, self.reset_view_btn,
            self.show_nulls_btn, self.show_duplicates_btn, self.show_outliers_btn,
            self.apply_filter_btn, self.sort_btn, self.generate_plots_btn, self.choose_visuals_btn,
            self.columns_spin, self.metric_select, self.date_select, self.scatter_x_select,
            self.scatter_y_select, self.scatter_color_select, self.category_select, self.category2_select,
            self.filter_column_select, self.filter_input, self.sort_column_select, self.sort_order_select,
            self.sql_run_btn
        ]
        for control in controls:
            control.setEnabled(enabled)

    def show_about(self):
        QMessageBox.about(self, 'О программе', f'''
            <h3>{APP_NAME} {APP_VERSION}</h3>
            <p>Настольное приложение для быстрого анализа и визуализации табличных данных.</p>
            <ul>
            <li>Профиль данных, оценка качества и автоматические инсайты</li>
            <li>13 видов графиков в светлой и тёмной теме</li>
            <li>SQL-запросы к загруженной таблице</li>
            <li>Экспорт данных, отчётов и графиков</li>
            </ul>
            <p>Автор: Arsenij Sadovskij · <a href="https://github.com/Sena22555">github.com/Sena22555</a></p>''')

    def show_shortcuts(self):
        rows = [('Ctrl+O', 'Открыть файл'), ('Ctrl+S', 'Сохранить данные'), ('Ctrl+I', 'Обновить сводку'),
                ('Ctrl+G', 'Построить графики'), ('Ctrl+1 / 2 / 3', 'Данные / Графики / SQL'),
                ('Ctrl+Enter', 'Выполнить SQL'), ('F11', 'Полноэкранный режим'), ('Ctrl+Q', 'Выход')]
        table = ''.join(f'<tr><td style="padding:3px 18px 3px 0"><b>{k}</b></td><td>{v}</td></tr>' for k, v in rows)
        QMessageBox.information(self, 'Горячие клавиши', f'<table>{table}</table>')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_F11:
            self.showNormal() if self.isFullScreen() else self.showFullScreen()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        self.save_settings()
        if self.conn:
            self.conn.close()
        event.accept()

    # ---------- загрузка ----------

    def dragEnterEvent(self, event):
        if self._dropped_file(event):
            event.acceptProposedAction()
            self._set_drop_active(True)

    def dragLeaveEvent(self, event):
        self._set_drop_active(False)

    def dropEvent(self, event):
        self._set_drop_active(False)
        path = self._dropped_file(event)
        if path:
            event.acceptProposedAction()
            self.load_path(path)

    def _dropped_file(self, event):
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path.lower().endswith(SUPPORTED_SUFFIXES):
                return path
        return None

    def _set_drop_active(self, active):
        self.drop_zone.setProperty('active', active)
        repolish(self.drop_zone)

    def load_file(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Открыть файл', str(Path.home()),
                                              'Таблицы (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls)')
        if path:
            self.load_path(path)

    def load_demo(self):
        self.load_path(resource_path('demo_data.csv'))

    def load_path(self, path):
        self.status_bar.showMessage(f'Загрузка {Path(path).name}…')
        self.set_ui_enabled(False)
        self.load_btn.setEnabled(False)
        self.worker = Worker(backend_load_file, path)
        self.worker.finished.connect(lambda df: self.on_file_loaded(df, path))
        self.worker.error.connect(self.on_file_error)
        self.worker.start()

    def on_file_loaded(self, df, path):
        self.load_btn.setEnabled(True)
        if df.empty:
            self.on_file_error('файл не содержит строк')
            return
        self.df = df
        self.current_file = Path(path).name
        self.subtitle.setText(self.current_file)
        self.setWindowTitle(f'{self.current_file} — {APP_NAME}')

        if self.conn:
            self.conn.close()
        # check_same_thread=False: запросы выполняются в фоновом потоке Worker
        self.conn = sqlite3.connect(':memory:', check_same_thread=False)

        self.update_column_selects()
        self.update_table(self.df)
        self.clear_plot_area()
        self.plot_stack.setCurrentIndex(0)
        self.data_stack.setCurrentIndex(1)
        self.tabs.setCurrentIndex(0)
        self.set_ui_enabled(True)
        self.show_summary()
        self.status_bar.showMessage(f'Загружено: {self.current_file} — {plural(len(df), ROWS)}, '
                                    f'{plural(df.shape[1], COLS)}')

    def on_file_error(self, err):
        self.load_btn.setEnabled(True)
        self.set_ui_enabled(not self.df.empty)
        self.status_bar.showMessage(f'Ошибка загрузки: {err}')
        QMessageBox.critical(self, 'Не удалось открыть файл', str(err))

    # ---------- таблица и фильтры ----------

    def update_table(self, df: pd.DataFrame):
        self.display_df = df.copy()
        self.model.update(self.display_df)
        self.table.resizeColumnsToContents()
        header = self.table.horizontalHeader()
        for col in range(self.model.columnCount()):
            header.resizeSection(col, min(max(header.sectionSize(col) + 16, 90), 280))
        self.sync_sql()
        self.update_data_info()

    def update_data_info(self):
        if self.df.empty:
            self.data_label.setText('Нет данных')
            return
        t = tokens(self.dark_theme)
        rows, cols = self.df.shape
        shown = len(self.display_df)
        nums = len(numeric_columns(self.df))
        cats = len(category_columns(self.df))
        missing_cells = int(self.df.isna().sum().sum())
        missing_pct = missing_cells / (rows * cols) * 100
        dupes = int(self.df.duplicated().sum())
        score = quality_score(self.df)

        fmt = lambda n: f'{n:,}'.replace(',', ' ')
        self.tile_rows.set(fmt(rows), 'все строки показаны' if shown == rows else f'показано {fmt(shown)}')
        self.tile_cols.set(str(cols), f'{nums} числовых · {cats} текстовых')
        self.tile_missing.set(f'{missing_pct:.1f}%', f'{fmt(missing_cells)} пустых ячеек')
        self.tile_dupes.set(fmt(dupes), f'{dupes / rows * 100:.1f}% строк' if dupes else 'повторов нет')
        if score >= 90:
            status, color = 'отлично', t['good']
        elif score >= 70:
            status, color = 'есть замечания', t['warning']
        else:
            status, color = 'нужна чистка', t['critical']
        self.tile_quality.set(f'{score}/100', status, color)

        self.table_hint.setText(f'{fmt(shown)} из {plural(rows, ROWS)}' if shown != rows else plural(rows, ROWS))
        self.data_label.setText(f'{fmt(rows)} × {cols}')

    def update_column_selects(self):
        """Заполняет списки колонок и подбирает осмысленные значения по умолчанию."""
        df = self.df
        columns = [str(c) for c in df.columns]
        nums = [str(c) for c in numeric_columns(df)]
        cats = [str(c) for c in category_columns(df)]
        groupable = [c for c in cats if 2 <= df[c].nunique() <= 12]

        dates = [c for c in cats if looks_like_date(df[c])]
        groupable = [c for c in groupable if c not in dates]

        metric = max(nums, key=lambda c: df[c].nunique()) if nums else None
        # для точечной диаграммы — самая сильная пара, но не почти дублирующие друг друга колонки
        pair = next((p for p in strongest_correlations(df, limit=20) if abs(p[2]) < 0.95), None)
        if pair:
            scatter_x, scatter_y = pair[0], pair[1]
        else:
            scatter_x = nums[0] if nums else None
            scatter_y = nums[1] if len(nums) > 1 else scatter_x
        ordered_groups = sorted(groupable, key=lambda c: df[c].nunique())
        color = ordered_groups[0] if ordered_groups else None
        multi = [c for c in groupable if df[c].nunique() >= 3] or groupable
        category = multi[0] if multi else (cats[0] if cats else None)
        category2 = next((c for c in multi if c != category), None)

        def fill(combo, items, default=None, placeholder=None):
            combo.blockSignals(True)
            combo.clear()
            if placeholder:
                combo.addItem(placeholder)
            combo.addItems(items)
            if default in items:
                combo.setCurrentText(default)
            combo.blockSignals(False)

        fill(self.filter_column_select, columns)
        fill(self.sort_column_select, columns, metric)
        fill(self.metric_select, nums, metric)
        fill(self.date_select, dates + [c for c in columns if c not in dates], dates[0] if dates else None)
        fill(self.scatter_x_select, nums, scatter_x)
        fill(self.scatter_y_select, nums, scatter_y)
        fill(self.scatter_color_select, cats, color, placeholder='Без группировки')
        fill(self.category_select, cats, category)
        fill(self.category2_select, cats, category2)

    def reset_view(self):
        self.filter_input.clear()
        if not self.df.empty:
            self.update_table(self.df)
            self.status_bar.showMessage('Фильтры сброшены, показаны все данные')

    def sort_data(self):
        if self.display_df.empty:
            return
        col = self.sort_column_select.currentText()
        if not col:
            return
        ascending = self.sort_order_select.currentIndex() == 0
        try:
            self.update_table(self.display_df.sort_values(by=col, ascending=ascending))
            direction = 'по возрастанию' if ascending else 'по убыванию'
            self.status_bar.showMessage(f'Отсортировано: {col}, {direction}')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка сортировки', str(e))

    def apply_filter(self):
        if self.df.empty:
            return
        col = self.filter_column_select.currentText()
        val = self.filter_input.text().strip()
        if not col or not val:
            self.update_table(self.df)
            return
        try:
            mask = self.df[col].astype(str).str.contains(val, case=False, na=False, regex=False)
            self.update_table(self.df[mask].copy())
            self.status_bar.showMessage(f'«{val}» в колонке {col}: найдено {plural(len(self.display_df), ROWS)}')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка фильтра', str(e))

    def show_null_rows(self):
        if self.df.empty:
            return
        filtered_df = self.df[self.df.isnull().any(axis=1)].copy()
        if filtered_df.empty:
            self.status_bar.showMessage('Строк с пропусками нет')
            return
        self.update_table(filtered_df)
        self.status_bar.showMessage(f'Строки с пропусками: {len(filtered_df)} из {len(self.df)}')

    def show_duplicate_rows(self):
        if self.df.empty:
            return
        filtered_df = self.df[self.df.duplicated(keep=False)].copy()
        if filtered_df.empty:
            self.status_bar.showMessage('Дубликатов нет')
            return
        self.update_table(filtered_df)
        self.status_bar.showMessage(f'Дубликаты: {len(filtered_df)} строк из {len(self.df)}')

    def show_outlier_rows(self):
        if self.df.empty:
            return
        outlier_indices = set()
        for series in detect_outliers(self.df).values():
            outlier_indices.update(series.index)
        if not outlier_indices:
            self.status_bar.showMessage('Выбросов не найдено')
            return
        filtered_df = self.df.loc[sorted(outlier_indices)].copy()
        self.update_table(filtered_df)
        self.status_bar.showMessage(f'Строки с выбросами: {len(filtered_df)} из {len(self.df)}')

    def delete_selected_rows(self, table=None, parent=None):
        table = table or self.table
        frame = table.model().dataframe()
        indexes = table.selectionModel().selectedRows() or table.selectionModel().selectedIndexes()
        rows = sorted({index.row() for index in indexes})
        if not rows:
            QMessageBox.information(parent or self, 'Удаление', 'Выберите строки для удаления.')
            return
        reply = QMessageBox.question(parent or self, 'Удаление', f'Удалить строк: {len(rows)}?',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.update_table(frame.drop(frame.index[rows]).reset_index(drop=True))
            self.status_bar.showMessage(f'Удалено строк: {len(rows)}')

    def delete_selected_columns(self, table=None, parent=None):
        table = table or self.table
        frame = table.model().dataframe()
        indexes = table.selectionModel().selectedIndexes()
        if not indexes:
            QMessageBox.information(parent or self, 'Удаление', 'Выберите колонки для удаления.')
            return
        col_names = [frame.columns[c] for c in sorted({i.column() for i in indexes})]
        reply = QMessageBox.question(parent or self, 'Удаление', f'Удалить колонки: {", ".join(map(str, col_names))}?',
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.update_table(frame.drop(columns=col_names))
            self.status_bar.showMessage(f'Удалены колонки: {", ".join(map(str, col_names))}')

    def show_table_context_menu(self, pos):
        menu = QMenu(self.table)
        copy_action = menu.addAction('Копировать')
        export_action = menu.addAction('Экспорт выделенного…')
        menu.addSeparator()
        del_row_action = menu.addAction('Удалить выбранные строки')
        del_col_action = menu.addAction('Удалить выбранные столбцы')

        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == del_row_action:
            self.delete_selected_rows()
        elif action == del_col_action:
            self.delete_selected_columns()
        elif action == copy_action:
            self.copy_selected_data()
        elif action == export_action:
            self.export_selected_data()

    def copy_selected_data(self):
        indexes = self.table.selectionModel().selectedIndexes()
        if not indexes:
            return
        frame = self.model.dataframe()
        rows = {}
        for index in indexes:
            rows.setdefault(index.row(), {})[index.column()] = str(frame.iat[index.row(), index.column()])
        text = '\n'.join('\t'.join(cells[c] for c in sorted(cells)) for _, cells in sorted(rows.items()))
        QApplication.clipboard().setText(text)
        self.status_bar.showMessage('Скопировано в буфер обмена')

    def export_selected_data(self):
        indexes = self.table.selectionModel().selectedIndexes()
        if not indexes:
            QMessageBox.information(self, 'Экспорт', 'Выберите строки для экспорта.')
            return
        selected = self.model.dataframe().iloc[sorted({i.row() for i in indexes})].copy()
        self._save_frame(selected, 'Экспорт выделенных строк')

    def detach_table(self):
        if self.display_df.empty:
            QMessageBox.information(self, 'Открепить таблицу', 'Нет данных для отображения.')
            return
        win = QMainWindow(self)
        win.setWindowTitle(f'{self.current_file or "Таблица"} — {APP_NAME}')
        win.resize(1000, 700)
        table = QTableView()
        configure_table(table)
        table.setSortingEnabled(True)
        table.setContextMenuPolicy(Qt.CustomContextMenu)
        table.setModel(PandasModel(self.display_df))
        table.resizeColumnsToContents()
        table.customContextMenuRequested.connect(lambda pos: self.show_detached_table_context_menu(pos, table, win))
        container = QWidget()
        container.setObjectName('Page')
        box = QVBoxLayout(container)
        box.setContentsMargins(12, 12, 12, 12)
        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(6, 6, 6, 6)
        card_layout.addWidget(table)
        box.addWidget(card)
        win.setCentralWidget(container)
        win.show()
        self.detached_windows.append(win)
        self.status_bar.showMessage('Таблица открыта в отдельном окне')

    def show_detached_table_context_menu(self, pos, table, window):
        menu = QMenu(window)
        del_row_action = menu.addAction('Удалить выбранные строки')
        del_col_action = menu.addAction('Удалить выбранные столбцы')
        action = menu.exec(table.viewport().mapToGlobal(pos))
        if action == del_row_action:
            self.delete_selected_rows(table, window)
        elif action == del_col_action:
            self.delete_selected_columns(table, window)
        if action:
            table.setModel(PandasModel(self.display_df))

    # ---------- сводка и инсайты ----------

    def show_summary(self):
        if self.df.empty:
            return
        self.setCursor(Qt.WaitCursor)
        try:
            self._insights = generate_insights(self.display_df)
            self._correlations = strongest_correlations(self.display_df, limit=4)
            self.render_insights()
            summary = numeric_summary(self.display_df)
            self.stats_model._right_aligned = set(summary.columns[1:])
            self.stats_model.update(summary)
            self.stats_hint.setText(f'числовых колонок: {len(summary)}' if len(summary) else 'числовых колонок нет')
            self.status_bar.showMessage('Сводка обновлена')
        except Exception as e:
            self.summary_text.setPlainText(f'Ошибка создания сводки: {e}')
        finally:
            self.unsetCursor()

    def render_insights(self):
        if not hasattr(self, 'summary_text'):
            return
        if not self._insights:
            self.summary_text.setHtml('')
            return
        t = tokens(self.dark_theme)
        blocks = []
        for key, value in self._insights.items():
            blocks.append(
                f'<p style="margin:0 0 1px 0; color:{t["muted"]}; font-size:12px;">{key}</p>'
                f'<p style="margin:0 0 12px 0; color:{t["text"]}; font-size:13px;">{value}</p>')
        if self._correlations:
            blocks.append(f'<p style="margin:6px 0 6px 0; color:{t["muted"]}; font-size:11px; '
                          f'font-weight:600; letter-spacing:1px;">СИЛЬНЕЙШИЕ СВЯЗИ</p>')
            for a, b, r in self._correlations:
                strength = 'сильная' if abs(r) > 0.7 else 'умеренная' if abs(r) > 0.3 else 'слабая'
                direction = 'прямая' if r > 0 else 'обратная'
                blocks.append(
                    f'<p style="margin:0 0 1px 0; color:{t["text"]};">{a} ↔ {b}</p>'
                    f'<p style="margin:0 0 10px 0; color:{t["text2"]}; font-size:12px;">'
                    f'r = {r:.2f} · {strength}, {direction}</p>')
        self.summary_text.setHtml(''.join(blocks))

    # ---------- графики ----------

    def update_visuals_hint(self):
        names = {vid: label for _, items in VISUALIZATIONS for vid, label in items}
        chosen = [names[v] for v in self.selected_visualizations if v in names]
        self.visuals_hint.setText(f'Выбрано: {len(chosen)} — ' + ', '.join(chosen).lower() if chosen
                                  else 'Графики не выбраны')

    def open_visual_selection(self):
        dlg = QDialog(self)
        dlg.setWindowTitle('Выбор графиков')
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(20, 18, 20, 16)
        layout.setSpacing(4)
        layout.addWidget(make_label('Какие графики построить', 'CardTitle'))
        layout.addWidget(make_label('Колонки для них задаются на панели слева.', 'Hint'))

        checks = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(28)
        grid.setVerticalSpacing(2)
        for i, (group, items) in enumerate(VISUALIZATIONS):
            column = QVBoxLayout()
            column.setSpacing(2)
            column.addSpacing(10)
            column.addWidget(make_label(group.upper(), 'SectionLabel'))
            for vid, label in items:
                cb = QCheckBox(label)
                cb.setChecked(vid in self.selected_visualizations)
                column.addWidget(cb)
                checks[vid] = cb
            column.addStretch()
            grid.addLayout(column, i // 2, i % 2)
        layout.addLayout(grid)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setProperty('variant', 'primary')
        buttons.button(QDialogButtonBox.Ok).setText('Готово')
        buttons.button(QDialogButtonBox.Cancel).setText('Отмена')
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addSpacing(12)
        layout.addWidget(buttons)

        if dlg.exec() == QDialog.Accepted:
            self.selected_visualizations = [vid for vid, cb in checks.items() if cb.isChecked()]
            self.update_visuals_hint()

    def plot_params(self):
        color = self.scatter_color_select.currentText()
        return {
            'metric': self.metric_select.currentText(),
            'date': self.date_select.currentText(),
            'x': self.scatter_x_select.currentText(),
            'y': self.scatter_y_select.currentText(),
            'color': None if self.scatter_color_select.currentIndex() <= 0 else color,
            'category': self.category_select.currentText(),
            'category2': self.category2_select.currentText(),
        }

    def generate_plots(self):
        if self.display_df.empty:
            QMessageBox.information(self, 'Графики', 'Сначала загрузите данные.')
            return
        if not self.selected_visualizations:
            QMessageBox.information(self, 'Графики', 'Выберите хотя бы один график.')
            return

        self.setCursor(Qt.WaitCursor)
        self.set_ui_enabled(False)
        self.plot_progress.setVisible(True)
        self.status_bar.showMessage('Строю графики…')
        # Параметры читаются в главном потоке, фигуры строятся в фоновом
        self.plot_worker = Worker(self.create_plot_figures, self.display_df.copy(),
                                  list(self.selected_visualizations), self.plot_params())
        self.plot_worker.finished.connect(self.on_plots_ready)
        self.plot_worker.error.connect(self.on_plots_error)
        self.plot_worker.start()

    @staticmethod
    def create_plot_figures(df, visualizations, p):
        if df.empty:
            raise ValueError('Нет данных для построения графиков')
        nums = numeric_columns(df)
        figures = []
        for vis in visualizations:
            try:
                if vis == 'hist' and p['metric'] in nums:
                    figures.append(plot_histograms(df[[p['metric']]]))
                elif vis == 'density' and p['metric'] in nums:
                    figures.append(plot_density(df, p['metric']))
                elif vis == 'box' and nums:
                    figures.append(plot_boxplot(df))
                elif vis == 'outliers' and p['metric'] in nums:
                    figures.append(plot_outliers(df, p['metric']))
                elif vis == 'distribution_comparison' and len(nums) >= 2:
                    chosen = [c for c in (p['x'], p['y']) if c in nums]
                    figures.append(plot_distribution_comparison(df, chosen if len(set(chosen)) == 2 else nums[:3]))
                elif vis == 'corr' and len(nums) >= 2:
                    figures.append(plot_correlation(df))
                elif vis == 'scatter' and p['x'] in nums and p['y'] in nums:
                    figures.append(plot_scatter(df, p['x'], p['y'], p['color']))
                elif vis == 'heatmap' and p['category'] in df.columns and p['category2'] in df.columns \
                        and p['metric'] in nums and p['category'] != p['category2']:
                    figures.append(plot_heatmap(df, p['category2'], p['category'], p['metric']))
                elif vis == 'bar' and p['category'] in df.columns:
                    figures.append(plot_bar_chart(df, p['category']))
                elif vis == 'pie' and p['category'] in df.columns:
                    figures.append(plot_pie_chart(df, p['category']))
                elif vis == 'line' and p['metric'] in nums:
                    figures.append(plot_line(df, p['metric']))
                elif vis == 'time_series' and p['date'] in df.columns and p['metric'] in nums:
                    figures.append(plot_time_series(df, p['date'], p['metric']))
                elif vis == 'missing':
                    figures.append(plot_missing_matrix(df))
            except Exception as e:
                print(f'Ошибка при создании графика {vis}: {e}')
        return figures

    def clear_plot_area(self):
        while self.plot_layout.count():
            widget = self.plot_layout.takeAt(0).widget()
            if widget:
                widget.setParent(None)
                widget.deleteLater()

    def on_plots_ready(self, figures):
        self.clear_plot_area()
        per_row = self.columns_spin.value()
        for column in range(4):
            self.plot_layout.setColumnStretch(column, 1 if column < per_row else 0)
        for index, fig in enumerate(figures):
            try:
                fig.set_layout_engine('tight')
            except Exception:
                pass
            canvas = FigureCanvas(fig)
            width, height = fig.get_size_inches()
            canvas.setMinimumHeight(int(min(560, max(320, 360 * height / max(width, 1) * 1.6))))
            canvas.setMinimumWidth(280)
            canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            card = make_card()
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)
            card_layout.addWidget(canvas)
            self.plot_layout.addWidget(card, index // per_row, index % per_row)

        self.set_ui_enabled(True)
        self.plot_progress.setVisible(False)
        self.unsetCursor()
        if figures:
            self.plot_stack.setCurrentIndex(1)
            self.tabs.setCurrentIndex(1)
            self.status_bar.showMessage(f'Построено графиков: {len(figures)}')
        else:
            self.plot_stack.setCurrentIndex(0)
            QMessageBox.information(self, 'Графики', 'Для выбранных графиков не хватает подходящих колонок.')

    def on_plots_error(self, err):
        self.set_ui_enabled(True)
        self.plot_progress.setVisible(False)
        self.unsetCursor()
        QMessageBox.critical(self, 'Ошибка графиков', f'Не удалось построить графики:\n{err}')

    def show_single_plot(self, fig, title):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.resize(820, 600)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(14, 14, 14, 12)
        card = make_card()
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 10, 10, 10)
        card_layout.addWidget(FigureCanvas(fig))
        layout.addWidget(card)
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.button(QDialogButtonBox.Close).setText('Закрыть')
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        dialog.exec()

    def analyze_outliers(self):
        if self.df.empty:
            QMessageBox.information(self, 'Анализ выбросов', 'Сначала загрузите данные.')
            return
        nums = numeric_columns(self.df)
        if not nums:
            QMessageBox.information(self, 'Анализ выбросов', 'Нет числовых колонок для анализа.')
            return
        current = nums.index(self.metric_select.currentText()) if self.metric_select.currentText() in nums else 0
        column, ok = QInputDialog.getItem(self, 'Анализ выбросов', 'Колонка:', nums, current, False)
        if not (ok and column):
            return
        try:
            values = self.df[column].dropna()
            outliers = detect_outliers(self.df[[column]]).get(column, pd.Series(dtype=float))
            share = len(outliers) / len(values) * 100 if len(values) else 0
            self.status_bar.showMessage(f'{column}: выбросов {len(outliers)} из {len(values)} ({share:.1f}%)')
            self.show_single_plot(plot_outliers(self.df, column), f'Выбросы: {column}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка анализа выбросов:\n{e}')

    def show_correlation_analysis(self):
        if self.df.empty:
            QMessageBox.information(self, 'Корреляционный анализ', 'Сначала загрузите данные.')
            return
        if len(numeric_columns(self.df)) < 2:
            QMessageBox.information(self, 'Корреляционный анализ', 'Нужно минимум 2 числовые колонки.')
            return
        try:
            self.show_single_plot(plot_correlation(self.df), 'Корреляционный анализ')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Ошибка корреляционного анализа:\n{e}')

    # ---------- SQL ----------

    def show_sql_templates(self):
        templates = {
            'Основные': [
                ('Все данные', 'SELECT * FROM data;'),
                ('Первые 10 строк', 'SELECT * FROM data LIMIT 10;'),
                ('Количество строк', 'SELECT COUNT(*) AS total_rows FROM data;'),
                ('Уникальные значения', 'SELECT DISTINCT column_name FROM data;'),
            ],
            'Фильтры': [
                ('По условию', "SELECT * FROM data WHERE column_name = 'value';"),
                ('Диапазон чисел', 'SELECT * FROM data WHERE numeric_column BETWEEN 10 AND 100;'),
                ('Поиск по тексту', "SELECT * FROM data WHERE text_column LIKE '%search%';"),
                ('Без пустых значений', 'SELECT * FROM data WHERE column_name IS NOT NULL;'),
            ],
            'Агрегация': [
                ('Группировка и подсчёт', 'SELECT column_name, COUNT(*) AS n FROM data GROUP BY column_name ORDER BY n DESC;'),
                ('Среднее', 'SELECT AVG(numeric_column) AS average FROM data;'),
                ('Минимум и максимум', 'SELECT MIN(column_name), MAX(column_name) FROM data;'),
                ('Сумма по группам', 'SELECT category, SUM(amount) FROM data GROUP BY category;'),
            ],
            'Сортировка': [
                ('По возрастанию', 'SELECT * FROM data ORDER BY column_name ASC;'),
                ('По убыванию', 'SELECT * FROM data ORDER BY column_name DESC;'),
                ('По двум колонкам', 'SELECT * FROM data ORDER BY col1 ASC, col2 DESC;'),
            ]
        }
        if not self.df.empty:
            cats = [c for c in category_columns(self.df) if self.df[c].nunique() <= 30]
            nums = numeric_columns(self.df)
            if cats and nums:
                templates = {'Для ваших данных': [
                    (f'Среднее «{nums[-1]}» по «{cats[0]}»',
                     f'SELECT "{cats[0]}", COUNT(*) AS n, ROUND(AVG("{nums[-1]}"), 1) AS avg\n'
                     f'FROM data\nGROUP BY "{cats[0]}"\nORDER BY avg DESC;'),
                    (f'Топ-10 по «{nums[-1]}»', f'SELECT * FROM data ORDER BY "{nums[-1]}" DESC LIMIT 10;'),
                    (f'Распределение «{cats[0]}»',
                     f'SELECT "{cats[0]}", COUNT(*) AS n FROM data GROUP BY 1 ORDER BY n DESC;'),
                ], **templates}

        dialog = QDialog(self)
        dialog.setWindowTitle('Шаблоны SQL')
        dialog.resize(560, 380)
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 14, 16, 12)
        tabs = QTabWidget()
        for category, queries in templates.items():
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.setContentsMargins(0, 12, 0, 0)
            for name, query in queries:
                btn = make_button(name, None, query, lambda checked=False, q=query: self.insert_sql_template(q, dialog))
                btn.setStyleSheet('text-align: left; padding-left: 14px;')
                tab_layout.addWidget(btn)
            tab_layout.addStretch()
            tabs.addTab(tab, category)
        layout.addWidget(tabs)
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.button(QDialogButtonBox.Close).setText('Закрыть')
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)
        dialog.exec()

    def insert_sql_template(self, query, dialog):
        self.sql_input.setPlainText(query)
        dialog.accept()

    def run_sql(self):
        if not self.conn:
            self.status_bar.showMessage('Сначала загрузите данные')
            return
        query = self.sql_input.toPlainText().strip()
        if not query:
            self.status_bar.showMessage('Пустой SQL-запрос')
            return
        self.sql_run_btn.setText('Выполняется…')
        self.sql_run_btn.setEnabled(False)
        self.sql_worker = Worker(pd.read_sql_query, query, self.conn)
        self.sql_worker.finished.connect(self.on_sql_finished)
        self.sql_worker.error.connect(self.on_sql_error)
        self.sql_worker.start()

    def on_sql_finished(self, df):
        self.sql_run_btn.setText('Выполнить')
        self.sql_run_btn.setEnabled(True)
        self.sql_result.setModel(PandasModel(df, editable=False))
        header = self.sql_result.horizontalHeader()
        if len(df.columns) <= 6:
            header.setSectionResizeMode(QHeaderView.Stretch)
        else:
            header.setSectionResizeMode(QHeaderView.Interactive)
            self.sql_result.resizeColumnsToContents()
        self.sql_hint.setText(f'{plural(len(df), ROWS)} · {plural(len(df.columns), COLS)}')
        self.status_bar.showMessage(f'Запрос выполнен: {plural(len(df), ROWS)}')

    def on_sql_error(self, err):
        self.sql_run_btn.setText('Выполнить')
        self.sql_run_btn.setEnabled(True)
        self.sql_hint.setText('ошибка в запросе')
        self.status_bar.showMessage(f'Ошибка SQL: {err}')
        QMessageBox.critical(self, 'Ошибка SQL', str(err))

    def sync_sql(self):
        """Синхронизирует SQLite-таблицу data с тем, что сейчас показано в таблице."""
        if self.conn and not self.display_df.empty:
            try:
                self.model.dataframe().to_sql('data', self.conn, index=False, if_exists='replace')
            except Exception as e:
                print(f'Ошибка синхронизации SQL: {e}')

    # ---------- сохранение и экспорт ----------

    def _save_frame(self, frame, title):
        path, _ = QFileDialog.getSaveFileName(self, title, str(Path.home() / 'data.csv'),
                                              'CSV (*.csv);;Excel (*.xlsx)')
        if not path:
            return
        try:
            if path.lower().endswith('.xlsx'):
                frame.to_excel(path, index=False)
            else:
                frame.to_csv(path, index=False)
            self.status_bar.showMessage(f'Сохранено: {Path(path).name}')
        except Exception as e:
            QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить файл:\n{e}')

    def save_data(self):
        if self.display_df.empty:
            QMessageBox.information(self, 'Сохранение', 'Нет данных для сохранения.')
            return
        self._save_frame(self.model.dataframe(), 'Сохранить данные')

    def export_report(self):
        if self.df.empty:
            self.status_bar.showMessage('Нет данных для экспорта')
            return
        folder = QFileDialog.getExistingDirectory(self, 'Папка для отчёта')
        if not folder:
            return
        try:
            report = generate_report(self.df)
            report['summary'].to_csv(Path(folder) / 'report_summary.csv')
            report['missing'].to_csv(Path(folder) / 'report_missing.csv')
            report['sample'].to_csv(Path(folder) / 'report_sample.csv')
            with open(Path(folder) / 'report_top_values.json', 'w', encoding='utf-8') as f:
                json.dump(report['top_values'], f, ensure_ascii=False, indent=2)
            with open(Path(folder) / 'report_profile.txt', 'w', encoding='utf-8') as f:
                f.write(create_data_profile_report(self.df))
            self.status_bar.showMessage(f'Отчёт сохранён в {folder}')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка экспорта', str(e))

    def save_plots(self):
        if self.df.empty:
            self.status_bar.showMessage('Нет данных для сохранения графиков')
            return
        folder = QFileDialog.getExistingDirectory(self, 'Папка для графиков')
        if not folder:
            return
        try:
            target_df = self.display_df if not self.display_df.empty else self.df
            figures = {'histograms.png': plot_histograms(target_df),
                       'correlation.png': plot_correlation(target_df),
                       'missing_matrix.png': plot_missing_matrix(target_df)}
            for name, fig in figures.items():
                fig.savefig(str(Path(folder) / name), dpi=200, bbox_inches='tight')
            self.status_bar.showMessage(f'Графики сохранены в {folder}')
        except Exception as e:
            QMessageBox.warning(self, 'Ошибка сохранения графиков', str(e))


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(resource_path(os.path.join('assets', 'icon.png'))))
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
