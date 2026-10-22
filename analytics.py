"""
Аналитическое ядро Analitik Pro: загрузка данных, статистика, инсайты и графики.

Графики строятся на объектах matplotlib.Figure (без pyplot), поэтому их можно
создавать в фоновом потоке. Оформление задаётся темой apply_chart_theme().
"""
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from cycler import cycler
from matplotlib import rcParams
from matplotlib.colors import LinearSegmentedColormap, ListedColormap, to_rgb
from matplotlib.figure import Figure
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter

# ============================================================
# Тема графиков
# ============================================================
# Категориальная палитра проверена на различимость при нарушениях цветового
# зрения (CVD ΔE ≥ 8 для соседних цветов) отдельно для светлой и тёмной поверхности.

CHART_THEMES = {
    'light': {
        'surface': '#fcfcfb', 'text': '#161615', 'text2': '#52514e', 'muted': '#898781',
        'grid': '#e9e8e2', 'axis': '#c3c2b7', 'empty': '#efeee9', 'other': '#b5b3ab',
        'critical': '#d03b3b',
        'series': ['#2a78d6', '#eb6834', '#1baf7a', '#eda100',
                   '#e87ba4', '#008300', '#6250d6', '#e34948'],
        'sequential': ['#e6f0fb', '#9ec5f4', '#5598e7', '#256abf', '#0d366b'],
        'diverging': ['#1c5cab', '#6da7ec', '#c9ddf5', '#f0efec', '#f5c4c3', '#e66767', '#a82f2f'],
    },
    'dark': {
        'surface': '#1a1a19', 'text': '#f0efec', 'text2': '#c3c2b7', 'muted': '#898781',
        'grid': '#2c2c2a', 'axis': '#383835', 'empty': '#262624', 'other': '#5a5955',
        'critical': '#e66767',
        'series': ['#3987e5', '#d95926', '#199e70', '#c98500',
                   '#d55181', '#008300', '#9085e9', '#e66767'],
        'sequential': ['#162a45', '#184f95', '#2a78d6', '#6da7ec', '#cde2fb'],
        'diverging': ['#9ec5f4', '#3987e5', '#1d3556', '#383835', '#5c2525', '#e34948', '#f4a3a2'],
    },
}

_theme = CHART_THEMES['light']


def apply_chart_theme(dark: bool) -> None:
    """Применяет тему ко всем графикам, которые будут созданы после вызова."""
    global _theme
    _theme = CHART_THEMES['dark' if dark else 'light']
    t = _theme
    rcParams.update({
        'figure.facecolor': t['surface'],
        'savefig.facecolor': t['surface'],
        'axes.facecolor': t['surface'],
        'axes.edgecolor': t['axis'],
        'axes.labelcolor': t['text2'],
        'axes.titlecolor': t['text'],
        'text.color': t['text'],
        'xtick.color': t['muted'],
        'ytick.color': t['muted'],
        'xtick.labelcolor': t['text2'],
        'ytick.labelcolor': t['text2'],
        'axes.grid': True,
        'axes.grid.axis': 'y',
        'axes.axisbelow': True,
        'grid.color': t['grid'],
        'grid.linewidth': 0.8,
        'axes.spines.top': False,
        'axes.spines.right': False,
        'axes.spines.left': False,
        'axes.prop_cycle': cycler(color=t['series']),
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
        'font.size': 9.5,
        'axes.titlesize': 11.5,
        'axes.titleweight': 'semibold',
        'axes.titlelocation': 'left',
        'axes.titlepad': 12,
        'axes.labelsize': 9.5,
        'axes.labelpad': 8,
        'xtick.major.size': 0,
        'ytick.major.size': 0,
        'xtick.major.pad': 6,
        'ytick.major.pad': 6,
        'legend.frameon': False,
        'legend.fontsize': 9,
        'legend.labelcolor': t['text2'],
        'lines.linewidth': 2,
        'patch.edgecolor': t['surface'],
        'figure.dpi': 100,
    })


def set_dark_theme():
    apply_chart_theme(True)


def set_light_theme():
    apply_chart_theme(False)


apply_chart_theme(False)


def _figure(width: float, height: float) -> Figure:
    return Figure(figsize=(width, height))


def _message_figure(text: str) -> Figure:
    fig = _figure(6, 3.6)
    fig.text(0.5, 0.5, text, ha='center', va='center', fontsize=11, color=_theme['muted'], wrap=True)
    return fig


def _sequential_cmap():
    return LinearSegmentedColormap.from_list('analitik_seq', _theme['sequential'])


def _diverging_cmap():
    return LinearSegmentedColormap.from_list('analitik_div', _theme['diverging'])


def _ink_for(rgba) -> str:
    """Цвет подписи, читаемый поверх ячейки заданного цвета."""
    r, g, b = to_rgb(rgba)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return '#161615' if luminance > 0.55 else '#f0efec'


def _number(value: float, _pos=None) -> str:
    if abs(value) >= 1000:
        return f'{value:,.0f}'.replace(',', ' ')
    return f'{value:g}'


def _numeric_axes(ax, x: bool = False, y: bool = False) -> None:
    if x:
        ax.xaxis.set_major_formatter(FuncFormatter(_number))
    if y:
        ax.yaxis.set_major_formatter(FuncFormatter(_number))


def _short(label: Any, limit: int = 18) -> str:
    text = str(label)
    return text if len(text) <= limit else text[:limit - 1] + '…'


# ============================================================
# Загрузка и типы колонок
# ============================================================

def load_file(path: str) -> pd.DataFrame:
    """Загружает CSV или Excel, подбирая кодировку для CSV."""
    p = str(path).lower()
    try:
        if p.endswith(('.xls', '.xlsx')):
            return pd.read_excel(path)
        return pd.read_csv(path, encoding='utf-8', on_bad_lines='skip', low_memory=False)
    except UnicodeDecodeError:
        try:
            return pd.read_csv(path, encoding='cp1251', on_bad_lines='skip', low_memory=False)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding='latin-1', on_bad_lines='skip', low_memory=False)
    except Exception as e:
        raise Exception(f"Ошибка загрузки файла: {str(e)}")


def numeric_columns(df: pd.DataFrame) -> List[str]:
    return [c for c in df.columns
            if pd.api.types.is_numeric_dtype(df[c]) and not pd.api.types.is_bool_dtype(df[c])]


def looks_like_date(series: pd.Series) -> bool:
    """Текстовая колонка, большинство значений которой — даты."""
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    if pd.api.types.is_numeric_dtype(series) or pd.api.types.is_bool_dtype(series):
        return False
    sample = series.dropna().astype(str).head(200)
    if sample.empty:
        return False
    return pd.to_datetime(sample, errors='coerce', format='mixed').notna().mean() > 0.8


def category_columns(df: pd.DataFrame) -> List[str]:
    """Текстовые, категориальные и логические колонки (в pandas 2 и 3)."""
    return [c for c in df.columns
            if pd.api.types.is_bool_dtype(df[c])
            or not (pd.api.types.is_numeric_dtype(df[c]) or pd.api.types.is_datetime64_any_dtype(df[c]))]


# ============================================================
# Отчёт
# ============================================================

def summary_table(df: pd.DataFrame) -> pd.DataFrame:
    desc = df.describe(include='all').transpose()
    desc['missing_pct'] = df.isna().mean() * 100
    desc['unique'] = df.nunique(dropna=False)
    return desc


def numeric_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Компактная статистика по числовым колонкам для таблицы в интерфейсе."""
    cols = numeric_columns(df)
    if not cols:
        return pd.DataFrame()
    nums = df[cols]
    table = pd.DataFrame({
        'Колонка': cols,
        'Заполнено': nums.notna().sum().values,
        'Среднее': nums.mean().values,
        'Медиана': nums.median().values,
        'Ст. откл.': nums.std().values,
        'Мин': nums.min().values,
        'Макс': nums.max().values,
        'Пропуски, %': (nums.isna().mean() * 100).values,
    })
    for col in ['Среднее', 'Медиана', 'Ст. откл.', 'Мин', 'Макс', 'Пропуски, %']:
        table[col] = table[col].map(lambda v: '' if pd.isna(v) else f'{v:,.2f}'.replace(',', ' '))
    return table


def top_values(df: pd.DataFrame, n: int = 5) -> Dict[str, Dict[Any, int]]:
    tops: Dict[str, Dict[Any, int]] = {}
    for col in df.columns:
        tops[col] = {str(k): int(v) for k, v in df[col].value_counts(dropna=False).head(n).items()}
    return tops


def missing_stats(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame({
        'missing_count': df.isna().sum(),
        'missing_pct': df.isna().mean() * 100
    })


def column_types(df: pd.DataFrame) -> pd.Series:
    return df.dtypes


def sample_rows(df: pd.DataFrame, n: int = 5) -> pd.DataFrame:
    return df.head(n)


def generate_report(df: pd.DataFrame) -> Dict[str, Any]:
    return {
        'summary': summary_table(df),
        'missing': missing_stats(df),
        'types': column_types(df),
        'top_values': top_values(df, n=5),
        'sample': sample_rows(df, n=5)
    }


def detect_outliers(df: pd.DataFrame, method: str = 'iqr') -> Dict[str, pd.Series]:
    """Находит выбросы в числовых колонках (IQR или z-оценка)."""
    outliers = {}
    for col in numeric_columns(df):
        data = df[col].dropna()
        if len(data) == 0:
            continue

        if method == 'iqr':
            q1 = data.quantile(0.25)
            q3 = data.quantile(0.75)
            iqr = q3 - q1
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            outliers[col] = data[(data < lower_bound) | (data > upper_bound)]
        elif method == 'zscore':
            z_scores = np.abs((data - data.mean()) / data.std())
            outliers[col] = data[z_scores > 3]

    return outliers


def strongest_correlations(df: pd.DataFrame, limit: int = 5) -> List[tuple]:
    """Пары числовых колонок с самой сильной корреляцией: (a, b, r)."""
    cols = numeric_columns(df)
    if len(cols) < 2:
        return []
    corr = df[cols].corr()
    pairs = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            r = corr.iloc[i, j]
            if not pd.isna(r):
                pairs.append((cols[i], cols[j], float(r)))
    pairs.sort(key=lambda p: abs(p[2]), reverse=True)
    return pairs[:limit]


def quality_score(df: pd.DataFrame) -> int:
    if df.empty:
        return 0
    missing_pct = df.isna().sum().sum() / (df.shape[0] * df.shape[1]) * 100
    duplicates = df.duplicated().sum()
    constant_cols = [c for c in df.columns if df[c].nunique() <= 1]
    score = 100
    if missing_pct > 10:
        score -= 20
    elif missing_pct > 2:
        score -= 8
    if duplicates > len(df) * 0.05:
        score -= 15
    elif duplicates > 0:
        score -= 5
    if constant_cols:
        score -= 10
    return max(score, 0)


# ============================================================
# Графики
# ============================================================

def plot_histograms(df: pd.DataFrame, numeric_only: bool = True, max_cols: int = 6) -> Figure:
    """Гистограммы числовых колонок (до max_cols штук в ряд)."""
    try:
        cols = (numeric_columns(df) if numeric_only else list(df.columns))[:max_cols]
        if not cols:
            return _message_figure('Нет числовых колонок для гистограмм')

        fig = _figure(max(6, 3.6 * len(cols)), 3.6)
        axes = fig.subplots(1, len(cols)) if len(cols) > 1 else [fig.subplots()]

        for ax, col in zip(axes, cols):
            data = df[col].dropna()
            if len(data) == 0:
                ax.text(0.5, 0.5, 'Нет данных', ha='center', va='center', transform=ax.transAxes,
                        color=_theme['muted'])
                continue
            bins = int(min(30, max(8, np.sqrt(len(data)))))
            ax.hist(data, bins=bins, color=_theme['series'][0], edgecolor=_theme['surface'], linewidth=1.2)
            ax.set_title(_short(col, 28) if len(cols) > 1 else f'Распределение: {col}')
            ax.set_ylabel('Частота' if ax is axes[0] else '')
            _numeric_axes(ax, x=True)

        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка построения гистограмм: {e}')


def plot_correlation(df: pd.DataFrame) -> Figure:
    """Матрица корреляций Пирсона с подписями значений."""
    try:
        cols = numeric_columns(df)[:20]
        if len(cols) < 2:
            return _message_figure('Для корреляции нужно минимум 2 числовые колонки')

        corr = df[cols].corr()
        if corr.isna().all().all():
            return _message_figure('Корреляцию вычислить невозможно')

        n = len(cols)
        size = max(5.2, min(10, 0.75 * n + 2.6))
        fig = _figure(size + 1, size)
        ax = fig.subplots()
        ax.grid(False)

        cmap = _diverging_cmap()
        mesh = ax.pcolormesh(corr.values, cmap=cmap, vmin=-1, vmax=1,
                             edgecolors=_theme['surface'], linewidth=2)
        ax.set_xlim(0, n)
        ax.set_ylim(n, 0)
        ax.set_xticks(np.arange(n) + 0.5)
        ax.set_yticks(np.arange(n) + 0.5)
        ax.set_xticklabels([_short(c, 14) for c in cols], rotation=40, ha='right')
        ax.set_yticklabels([_short(c, 18) for c in cols])
        ax.spines['bottom'].set_visible(False)

        if n <= 12:
            for i in range(n):
                for j in range(n):
                    value = corr.values[i, j]
                    if pd.isna(value):
                        continue
                    ax.text(j + 0.5, i + 0.5, f'{value:.2f}', ha='center', va='center', fontsize=8.5,
                            color=_ink_for(cmap((value + 1) / 2)))

        cbar = fig.colorbar(mesh, ax=ax, shrink=0.75, pad=0.03)
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(length=0)
        ax.set_title('Корреляции между числовыми колонками')
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка построения корреляции: {e}')


def plot_missing_matrix(df: pd.DataFrame) -> Figure:
    """Карта пропусков: каждая полоса — колонка, отметки — пропущенные значения."""
    try:
        if df.empty:
            return _message_figure('Нет данных для анализа пропусков')

        sample_df = df.sample(n=1000, random_state=0).sort_index() if len(df) > 1000 else df
        m = sample_df.isna().astype(int)

        fig = _figure(min(12, max(6.5, m.shape[1] * 0.5 + 3)), min(8, max(3.6, m.shape[1] * 0.32 + 1.6)))
        ax = fig.subplots()
        ax.grid(False)
        cmap = ListedColormap([_theme['empty'], _theme['critical']])
        ax.imshow(m.T.values, aspect='auto', cmap=cmap, vmin=0, vmax=1, interpolation='nearest')
        ax.set_yticks(range(len(m.columns)))
        ax.set_yticklabels([_short(c, 22) for c in m.columns])
        ax.set_xlabel('Строки' + (' (выборка 1000)' if len(df) > 1000 else ''))
        ax.spines['bottom'].set_visible(False)

        total = int(df.isna().sum().sum())
        ax.set_title(f'Карта пропусков · {total:,} пустых ячеек'.replace(',', ' '))
        ax.legend(handles=[Patch(color=_theme['critical'], label='Пропуск'),
                           Patch(color=_theme['empty'], label='Есть значение')],
                  loc='upper right', bbox_to_anchor=(1, 1.13), ncol=2, handlelength=1, handleheight=1)
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка построения карты пропусков: {e}')


def plot_pie_chart(df: pd.DataFrame, column: str, top_n: int = 8) -> Figure:
    """Кольцевая диаграмма долей: топ значений, остальное — «Другое»."""
    counts = df[column].astype(str).value_counts()
    if counts.empty:
        return _message_figure('Нет данных для диаграммы')
    if len(counts) > top_n:
        head = counts.head(top_n - 1)
        counts = pd.concat([head, pd.Series({'Другое': counts.iloc[top_n - 1:].sum()})])

    colors = list(_theme['series'][:len(counts)])
    if 'Другое' in counts.index:
        colors[-1] = _theme['other']

    fig = _figure(6.6, 4.4)
    ax = fig.subplots()
    ax.pie(counts.values, colors=colors, startangle=90, counterclock=False,
           wedgeprops={'width': 0.36, 'edgecolor': _theme['surface'], 'linewidth': 2})
    total = int(counts.sum())
    ax.text(0, 0.08, f'{total:,}'.replace(',', ' '), ha='center', va='center', fontsize=17, fontweight='semibold')
    ax.text(0, -0.16, 'записей', ha='center', va='center', fontsize=9, color=_theme['muted'])
    labels = [f'{_short(k, 20)}  {v / total * 100:.0f}%' for k, v in counts.items()]
    ax.legend(labels=labels, loc='center left', bbox_to_anchor=(1.0, 0.5), handlelength=1, handleheight=1)
    ax.set_title(f'Доли: {column}')
    ax.axis('equal')
    fig.tight_layout()
    return fig


def plot_bar_chart(df: pd.DataFrame, column: str, top_n: int = 10) -> Figure:
    """Горизонтальные столбцы: самые частые значения колонки."""
    counts = df[column].astype(str).value_counts().head(top_n)
    if counts.empty:
        return _message_figure('Нет данных для столбчатой диаграммы')

    fig = _figure(7, max(3.2, 0.42 * len(counts) + 1.4))
    ax = fig.subplots()
    ax.grid(axis='y', visible=False)
    ax.grid(axis='x', visible=True)
    labels = [_short(i, 24) for i in counts.index[::-1]]
    values = counts.values[::-1]
    ax.barh(labels, values, height=0.68, color=_theme['series'][0])
    for y, v in enumerate(values):
        ax.text(v, y, f'  {v:,}'.replace(',', ' '), va='center', ha='left', fontsize=9, color=_theme['text2'])
    ax.set_xlim(0, values.max() * 1.15)
    _numeric_axes(ax, x=True)
    ax.spines['bottom'].set_visible(False)
    ax.set_title(f'Самые частые значения: {column}')
    ax.set_xlabel('Количество')
    fig.tight_layout()
    return fig


def plot_scatter(df: pd.DataFrame, x_col: str, y_col: str, color_col: str | None = None) -> Figure:
    """Точечная диаграмма; с группировкой — до трёх групп цветом, остальные в «Другое»."""
    fig = _figure(6.6, 4.6)
    ax = fig.subplots()
    ax.grid(axis='x', visible=True)
    ring = {'edgecolors': _theme['surface'], 'linewidths': 0.8}

    if color_col and color_col in df.columns and color_col not in (x_col, y_col):
        data = df[[x_col, y_col, color_col]].dropna()
        groups = data[color_col].astype(str)
        leaders = groups.value_counts().index[:3]
        other = data[~groups.isin(leaders)]
        if len(other):
            ax.scatter(other[x_col], other[y_col], s=36, alpha=0.6, color=_theme['other'], label='Другое', **ring)
        for i, name in enumerate(leaders):
            part = data[groups == name]
            ax.scatter(part[x_col], part[y_col], s=40, alpha=0.9, color=_theme['series'][i],
                       label=_short(name, 20), **ring)
        ax.legend(title=color_col, title_fontsize=9, loc='best')
    else:
        data = df[[x_col, y_col]].dropna()
        ax.scatter(data[x_col], data[y_col], s=40, alpha=0.85, color=_theme['series'][0], **ring)

    _numeric_axes(ax, x=True, y=True)
    ax.set_title(f'{y_col} и {x_col}')
    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    fig.tight_layout()
    return fig


def _style_boxplot(bp, color):
    for box in bp['boxes']:
        box.set_facecolor(color)
        box.set_alpha(0.22)
        box.set_edgecolor(color)
        box.set_linewidth(1.5)
    for key in ('whiskers', 'caps'):
        for line in bp[key]:
            line.set_color(_theme['muted'])
            line.set_linewidth(1.2)
    for median in bp['medians']:
        median.set_color(color)
        median.set_linewidth(2.2)
    for flier in bp['fliers']:
        flier.set_marker('o')
        flier.set_markersize(5)
        flier.set_markerfacecolor(_theme['muted'])
        flier.set_markeredgecolor(_theme['surface'])
        flier.set_alpha(0.8)


def plot_boxplot(df: pd.DataFrame, columns: list | None = None) -> Figure:
    """Ящики с усами: у каждой колонки своя шкала, чтобы разные единицы не сплющивали друг друга."""
    nums = numeric_columns(df)
    cols = nums if columns is None else [c for c in columns if c in nums]
    cols = cols[:6]
    if not cols:
        return _message_figure('Нет числовых колонок для диаграммы размаха')
    fig = _figure(max(6, 2.1 * len(cols)), 4.2)
    axes = fig.subplots(1, len(cols)) if len(cols) > 1 else [fig.subplots()]
    for ax, col in zip(axes, cols):
        bp = ax.boxplot(df[col].dropna(), patch_artist=True, widths=0.5)
        _style_boxplot(bp, _theme['series'][0])
        ax.set_xticks([1], labels=[_short(col, 14)])
        _numeric_axes(ax, y=True)
    fig.suptitle('Размах значений', x=0.01, ha='left', fontsize=11.5, fontweight='semibold', color=_theme['text'])
    fig.tight_layout()
    return fig


def _kde(values: np.ndarray, points: int = 256):
    """Оценка плотности гауссовым ядром (правило Скотта), без зависимости от SciPy."""
    values = values[np.isfinite(values)]
    std = values.std(ddof=1) if len(values) > 1 else 0
    if std == 0:
        return None, None
    bandwidth = std * len(values) ** (-1 / 5)
    grid = np.linspace(values.min() - 3 * bandwidth, values.max() + 3 * bandwidth, points)
    sample = values if len(values) <= 5000 else np.random.default_rng(0).choice(values, 5000, replace=False)
    density = np.exp(-0.5 * ((grid[:, None] - sample[None, :]) / bandwidth) ** 2).sum(axis=1)
    density /= len(sample) * bandwidth * np.sqrt(2 * np.pi)
    return grid, density


def plot_density(df: pd.DataFrame, column: str) -> Figure:
    """Сглаженное распределение (KDE)."""
    if column not in df.columns or df[column].dropna().empty:
        return _message_figure('Недостаточно данных для плотности')
    grid, density = _kde(df[column].dropna().to_numpy(dtype=float))
    if grid is None:
        return _message_figure('Все значения одинаковые — плотность не определена')
    color = _theme['series'][0]
    fig = _figure(6.6, 4)
    ax = fig.subplots()
    ax.fill_between(grid, density, color=color, alpha=0.16, linewidth=0)
    ax.plot(grid, density, color=color)
    ax.set_ylim(bottom=0)
    ax.set_yticklabels([])
    _numeric_axes(ax, x=True)
    ax.set_title(f'Плотность распределения: {column}')
    ax.set_xlabel(column)
    fig.tight_layout()
    return fig


def plot_line(df: pd.DataFrame, column: str) -> Figure:
    """Значения колонки по порядку строк."""
    if column not in df.columns or df[column].dropna().empty:
        return _message_figure('Недостаточно данных для линейного графика')
    fig = _figure(8, 3.8)
    ax = fig.subplots()
    ax.plot(range(len(df)), df[column].to_numpy(), color=_theme['series'][0])
    _numeric_axes(ax, y=True)
    ax.set_title(f'{column} по строкам')
    ax.set_xlabel('Номер строки')
    ax.set_ylabel(column)
    fig.tight_layout()
    return fig


def plot_outliers(df: pd.DataFrame, column: str) -> Figure:
    """Диаграмма размаха с выделенными выбросами (правило 1,5 IQR)."""
    try:
        if column not in df.columns:
            return _message_figure(f'Колонка «{column}» не найдена')
        data = df[column].dropna()
        if len(data) == 0:
            return _message_figure('Нет данных для анализа выбросов')

        fig = _figure(6.6, 4.4)
        ax = fig.subplots()
        bp = ax.boxplot(data, patch_artist=True, widths=0.45, showfliers=False)
        _style_boxplot(bp, _theme['series'][0])

        outliers = detect_outliers(df[[column]], 'iqr').get(column, pd.Series(dtype=float))
        if len(outliers) > 0:
            jitter = np.random.default_rng(0).uniform(-0.06, 0.06, len(outliers))
            ax.scatter(1 + jitter, outliers, s=42, color=_theme['critical'],
                       edgecolors=_theme['surface'], linewidths=0.8, label=f'Выбросы: {len(outliers)}')
            ax.legend(loc='upper right')

        ax.set_xticks([1], labels=[_short(column, 24)])
        _numeric_axes(ax, y=True)
        ax.set_title(f'Выбросы: {column}')
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка анализа выбросов: {e}')


def plot_distribution_comparison(df: pd.DataFrame, columns: List[str]) -> Figure:
    """Плотности нескольких числовых колонок на одной оси."""
    try:
        nums = [c for c in columns if c in numeric_columns(df)][:3]
        if len(nums) < 2:
            return _message_figure('Нужно минимум 2 числовые колонки')
        fig = _figure(8, 4.4)
        ax = fig.subplots()
        for i, col in enumerate(nums):
            grid, density = _kde(df[col].dropna().to_numpy(dtype=float))
            if grid is not None:
                ax.plot(grid, density, color=_theme['series'][i], label=col)
        ax.set_ylim(bottom=0)
        ax.set_yticklabels([])
        ax.set_title('Сравнение распределений')
        ax.legend()
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка сравнения распределений: {e}')


def plot_time_series(df: pd.DataFrame, date_col: str, value_col: str) -> Figure:
    """Значение по датам."""
    try:
        if date_col not in df.columns or value_col not in df.columns:
            return _message_figure('Указанные колонки не найдены')
        dates = pd.to_datetime(df[date_col], errors='coerce')
        if dates.notna().sum() < 2:
            return _message_figure(f'Колонка «{date_col}» не похожа на дату.\nВыберите колонку с датами в поле X.')

        data = pd.DataFrame({'date': dates, 'value': df[value_col]}).dropna().sort_values('date')
        fig = _figure(9, 4)
        ax = fig.subplots()
        color = _theme['series'][0]
        ax.plot(data['date'], data['value'], color=color,
                marker='o' if len(data) <= 60 else None, markersize=5,
                markeredgecolor=_theme['surface'], markeredgewidth=1)
        _numeric_axes(ax, y=True)
        ax.set_title(f'{value_col} по датам')
        ax.set_ylabel(value_col)
        fig.autofmt_xdate(rotation=30)
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка временного ряда: {e}')


def plot_heatmap(df: pd.DataFrame, x_col: str, y_col: str, value_col: str) -> Figure:
    """Тепловая карта среднего значения по двум измерениям."""
    try:
        if not all(col in df.columns for col in [x_col, y_col, value_col]):
            return _message_figure('Не все колонки найдены')
        pivot = df.pivot_table(values=value_col, index=y_col, columns=x_col, aggfunc='mean')
        if pivot.empty:
            return _message_figure('Недостаточно данных для тепловой карты')
        pivot = pivot.iloc[:25, :25]

        rows, cols = pivot.shape
        fig = _figure(min(12, max(6, cols * 0.7 + 3)), min(9, max(4, rows * 0.45 + 2)))
        ax = fig.subplots()
        ax.grid(False)
        cmap = _sequential_cmap()
        values = pivot.values
        mesh = ax.pcolormesh(values, cmap=cmap, edgecolors=_theme['surface'], linewidth=2)
        ax.set_xlim(0, cols)
        ax.set_ylim(rows, 0)
        ax.set_xticks(np.arange(cols) + 0.5)
        ax.set_yticks(np.arange(rows) + 0.5)
        ax.set_xticklabels([_short(c, 12) for c in pivot.columns], rotation=40, ha='right')
        ax.set_yticklabels([_short(r, 18) for r in pivot.index])
        ax.spines['bottom'].set_visible(False)

        if rows * cols <= 80:
            lo, hi = np.nanmin(values), np.nanmax(values)
            for i in range(rows):
                for j in range(cols):
                    v = values[i, j]
                    if np.isnan(v):
                        continue
                    share = 0.5 if hi == lo else (v - lo) / (hi - lo)
                    ax.text(j + 0.5, i + 0.5, f'{v:,.0f}'.replace(',', ' ') if abs(v) >= 100 else f'{v:.2f}',
                            ha='center', va='center', fontsize=8, color=_ink_for(cmap(share)))

        cbar = fig.colorbar(mesh, ax=ax, shrink=0.75, pad=0.03)
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(length=0)
        cbar.set_label(f'Среднее: {value_col}')
        ax.set_title(f'{value_col}: {y_col} × {x_col}')
        ax.set_xlabel(x_col)
        ax.set_ylabel(y_col)
        fig.tight_layout()
        return fig
    except Exception as e:
        return _message_figure(f'Ошибка тепловой карты: {e}')


# ============================================================
# Инсайты
# ============================================================

def generate_insights(df: pd.DataFrame) -> Dict[str, str]:
    """Автоматические наблюдения о данных."""
    insights = {}

    try:
        insights['Размер данных'] = f"{df.shape[0]:,} × {df.shape[1]} (строки × колонки)".replace(',', ' ')

        missing_pct = (df.isnull().sum().sum() / (df.shape[0] * df.shape[1])) * 100
        insights['Пропуски'] = f"{missing_pct:.1f}% всех ячеек"

        nums = numeric_columns(df)
        if nums:
            insights['Числовые колонки'] = f"{len(nums)} из {df.shape[1]}"

            outliers = detect_outliers(df)
            total_outliers = sum(len(outliers[col]) for col in outliers)
            insights['Выбросы'] = f"{total_outliers} значений за пределами 1.5 IQR"

            strong = [p for p in strongest_correlations(df, limit=50) if abs(p[2]) > 0.7]
            if strong:
                a, b, r = strong[0]
                insights['Сильные корреляции'] = f"{a} ↔ {b}: r = {r:.2f} (сильных пар: {len(strong)})"

        cats = [c for c in category_columns(df)
                if not pd.api.types.is_bool_dtype(df[c]) and not looks_like_date(df[c])]
        if cats:
            insights['Категориальные колонки'] = f"{len(cats)} из {df.shape[1]}"

            high_cardinality = [col for col in cats if df[col].nunique() > df.shape[0] * 0.8]
            if high_cardinality:
                insights['Высокая кардинальность'] = f"{', '.join(map(str, high_cardinality[:3]))} — похоже на ID"

        duplicates = df.duplicated().sum()
        if duplicates > 0:
            insights['Дубликаты'] = f"{duplicates / len(df) * 100:.1f}% строк ({duplicates} шт.)"

        constant_cols = [col for col in df.columns if df[col].nunique() <= 1]
        if constant_cols:
            insights['Константные колонки'] = f"{len(constant_cols)} (можно удалить)"

        insights['Оценка качества'] = f"{quality_score(df)}/100"

    except Exception as e:
        insights['Ошибка'] = f"Ошибка анализа: {str(e)}"

    return insights


def create_data_profile_report(df: pd.DataFrame) -> str:
    """Текстовый профиль данных для экспорта."""
    try:
        lines = ["=" * 60, "ПРОФИЛЬ ДАННЫХ", "=" * 60]
        lines.append(f"Размер: {df.shape[0]:,} строк × {df.shape[1]} колонок")
        lines.append(f"Память: {df.memory_usage(deep=True).sum() / 1024 / 1024:.1f} МБ")

        lines.append("\nТИПЫ ДАННЫХ:")
        for dtype, count in df.dtypes.astype(str).value_counts().items():
            lines.append(f"  • {dtype}: {count} колонок")

        missing_total = df.isnull().sum().sum()
        missing_pct = (missing_total / (df.shape[0] * df.shape[1])) * 100
        lines.append(f"\nПРОПУСКИ: {missing_total:,} ({missing_pct:.1f}%)")
        missing_cols = df.isnull().sum()
        missing_cols = missing_cols[missing_cols > 0].sort_values(ascending=False)
        for col, count in missing_cols.head(5).items():
            lines.append(f"    • {col}: {count:,} ({count / len(df) * 100:.1f}%)")

        duplicates = df.duplicated().sum()
        if duplicates > 0:
            lines.append(f"\nДУБЛИКАТЫ: {duplicates:,} строк ({duplicates / len(df) * 100:.1f}%)")

        nums = numeric_columns(df)
        if nums:
            lines.append(f"\nЧИСЛОВЫЕ КОЛОНКИ ({len(nums)}):")
            for col in nums[:10]:
                data = df[col].dropna()
                if len(data) > 0:
                    lines.append(f"  • {col}: мин={data.min():.2f}, макс={data.max():.2f}, среднее={data.mean():.2f}")

        cats = category_columns(df)
        if cats:
            lines.append(f"\nКАТЕГОРИАЛЬНЫЕ КОЛОНКИ ({len(cats)}):")
            for col in cats[:10]:
                mode = df[col].mode()
                most_common = mode.iloc[0] if len(mode) > 0 else "—"
                lines.append(f"  • {col}: {df[col].nunique()} уникальных, чаще всего «{most_common}»")

        corr = strongest_correlations(df, limit=5)
        if corr:
            lines.append("\nСИЛЬНЕЙШИЕ КОРРЕЛЯЦИИ:")
            for a, b, r in corr:
                lines.append(f"  • {a} ↔ {b}: r = {r:.3f}")

        lines.append(f"\nОЦЕНКА КАЧЕСТВА: {quality_score(df)}/100")
        lines.append("=" * 60)
        return "\n".join(lines)

    except Exception as e:
        return f"Ошибка создания профиля: {str(e)}"
