"""Собрать SQLite и картинки карт потока для первой защиты.

Цифры сценария берутся из backend.engine на data/venio_factory.json.
Нормативы не подменяются. Идеальная карта не получает выдуманные секунды.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JSON_PATH = ROOT / "data" / "venio_factory.json"
DB_PATH = ROOT / "data" / "venio_stage1.sqlite"
DIAGRAMS = ROOT / "analysis" / "diagrams"

OPS = [
    ("o1", "1. Корпус и нижняя крышка", 83),
    ("o2", "2. Корпус и верхняя крышка", 66),
    ("o3", "3. Сборка дросселя", 13),
    ("o4", "4. Тарелка и дроссель", 61),
    ("o5", "5. Сборка мембраны", 35),
    ("o6", "6. Сборка пробки", 39),
    ("o7", "7. Сборка пульта", 102),
    ("o8", "8. Шесть болтов", 171),
    ("o9", "9. Штуцеры и патрубок", 82),
    ("qc", "ОТК", 22),
]


def load_model():
    return json.loads(JSON_PATH.read_text(encoding="utf8"))


def build_database(path: Path = DB_PATH) -> None:
    import sys
    sys.path.insert(0, str(ROOT))
    from backend.engine import compare

    model = load_model()
    scenario = json.loads(json.dumps(model))
    for node in scenario["nodes"]:
        if node["id"] == "o8":
            node["cycle_s"] = 120
            node["cycle_basis"] = "changed_as_scenario"
    compared = compare(model, scenario)
    if path.exists():
        path.unlink()
    connection = sqlite3.connect(path)
    connection.executescript(
        """
        CREATE TABLE process_model (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            product TEXT NOT NULL,
            status TEXT NOT NULL,
            schema_version INTEGER NOT NULL
        );
        CREATE TABLE node (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL REFERENCES process_model(id),
            name TEXT NOT NULL,
            kind TEXT NOT NULL,
            cycle_s REAL,
            workers INTEGER,
            defect_pct REAL,
            cycle_basis TEXT,
            evidence TEXT
        );
        CREATE TABLE material_edge (
            id INTEGER PRIMARY KEY,
            model_id TEXT NOT NULL REFERENCES process_model(id),
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            category TEXT NOT NULL,
            verification TEXT,
            evidence TEXT
        );
        CREATE TABLE info_signal (
            id INTEGER PRIMARY KEY,
            model_id TEXT NOT NULL REFERENCES process_model(id),
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            message TEXT NOT NULL,
            evidence TEXT
        );
        CREATE TABLE scenario_settings (
            model_id TEXT PRIMARY KEY REFERENCES process_model(id),
            shift_s INTEGER NOT NULL,
            takt_s INTEGER NOT NULL,
            target_units INTEGER NOT NULL,
            transport_batch INTEGER NOT NULL,
            travel_s REAL NOT NULL,
            unit_material_cost REAL,
            unit_sale_price REAL
        );
        CREATE TABLE evidence_reference (
            id INTEGER PRIMARY KEY,
            model_id TEXT NOT NULL REFERENCES process_model(id),
            subject TEXT NOT NULL,
            document TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE scenario_result (
            id TEXT PRIMARY KEY,
            model_id TEXT NOT NULL REFERENCES process_model(id),
            label TEXT NOT NULL,
            accepted INTEGER NOT NULL,
            throughput_units_hour REAL NOT NULL,
            theoretical_critical_path_s REAL NOT NULL,
            bottleneck_id TEXT NOT NULL,
            bottleneck_cycle_s REAL NOT NULL,
            finance_status TEXT NOT NULL,
            caveat TEXT NOT NULL
        );
        CREATE TABLE operation_result (
            id INTEGER PRIMARY KEY,
            scenario_id TEXT NOT NULL REFERENCES scenario_result(id),
            node_id TEXT NOT NULL,
            completed INTEGER NOT NULL,
            utilization_pct REAL NOT NULL,
            capacity_units_hour REAL NOT NULL
        );
        """
    )
    connection.execute(
        "INSERT INTO process_model VALUES (?,?,?,?,?)",
        (model["id"], model["name"], model["product"], model["status"], model["schema_version"]),
    )
    for node in model["nodes"]:
        connection.execute(
            "INSERT INTO node VALUES (?,?,?,?,?,?,?,?,?)",
            (
                node["id"], model["id"], node["name"], node["kind"],
                node.get("cycle_s"), node.get("workers"), node.get("defect_pct"),
                node.get("cycle_basis"), node.get("evidence"),
            ),
        )
        if node.get("evidence"):
            connection.execute(
                "INSERT INTO evidence_reference (model_id, subject, document, status) VALUES (?,?,?,?)",
                (model["id"], node["id"], node["evidence"], node.get("cycle_basis") or "described"),
            )
    for edge in model["edges"]:
        connection.execute(
            "INSERT INTO material_edge (model_id, from_id, to_id, category, verification, evidence) VALUES (?,?,?,?,?,?)",
            (model["id"], edge["from"], edge["to"], edge["category"], edge.get("verification"), edge.get("evidence")),
        )
    for signal in model["info_flow"]:
        connection.execute(
            "INSERT INTO info_signal (model_id, from_id, to_id, message, evidence) VALUES (?,?,?,?,?)",
            (model["id"], signal["from"], signal["to"], signal["message"], signal.get("evidence")),
        )
    settings = model["settings"]
    connection.execute(
        "INSERT INTO scenario_settings VALUES (?,?,?,?,?,?,?,?)",
        (
            model["id"], settings["shift_s"], settings["takt_s"], settings["target_units"],
            settings["transport_batch"], settings["travel_s"],
            settings["unit_material_cost"], settings["unit_sale_price"],
        ),
    )
    for key, label in (("baseline", "как есть, нормативы"), ("scenario", "гипотеза: операция 8 равна 120 с")):
        row = compared[key]
        connection.execute(
            "INSERT INTO scenario_result VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                key, model["id"], label, row["accepted"], row["throughput_units_hour"],
                row["theoretical_critical_path_s"], row["potential_bottleneck"]["id"],
                row["potential_bottleneck"]["cycle_s"], row["financial"]["status"],
                compared["caveat"],
            ),
        )
        for operation in row["operations"]:
            connection.execute(
                "INSERT INTO operation_result (scenario_id, node_id, completed, utilization_pct, capacity_units_hour) VALUES (?,?,?,?,?)",
                (key, operation["id"], operation["completed"], operation["utilization_pct"], operation["capacity_units_hour"]),
            )
    connection.commit()
    connection.close()


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _box(x, y, title, lines, fill="#fff", stroke="#1f2933", title_fill="#102a43"):
    height = 28 + 16 * len(lines)
    parts = [
        f'<rect x="{x}" y="{y}" width="168" height="{height}" rx="4" fill="{fill}" stroke="{stroke}" stroke-width="1.4"/>',
        f'<text x="{x+8}" y="{y+18}" font-size="12" font-weight="700" fill="{title_fill}">{_esc(title)}</text>',
    ]
    for index, line in enumerate(lines):
        parts.append(f'<text x="{x+8}" y="{y+36+index*16}" font-size="11" fill="#243b53">{_esc(line)}</text>')
    return "\n".join(parts), height


def _arrow(x1, y1, x2, y2, dashed=False, color="#243b53"):
    dash = ' stroke-dasharray="5 4"' if dashed else ""
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="1.6"{dash} '
        f'marker-end="url(#arrow)"/>'
    )


def _header(title, subtitle):
    return f'''<text x="24" y="28" font-size="18" font-weight="700" fill="#102a43">{_esc(title)}</text>
<text x="24" y="48" font-size="12" fill="#334e68">{_esc(subtitle)}</text>
<text x="24" y="68" font-size="12" fill="#334e68">Такт 120 с = 1200 с / 10 шт. Партия логиста: 2. ВПП, НЗП, брак, рейс и деньги: не измерено.</text>'''


def _legend():
    return '''<g font-size="11" fill="#243b53">
<rect x="24" y="84" width="14" height="10" fill="#fff" stroke="#1f2933"/>
<text x="42" y="93">операция</text>
<line x1="120" y1="89" x2="160" y2="89" stroke="#243b53" stroke-width="2"/>
<text x="166" y="93">материальный поток</text>
<line x1="320" y1="89" x2="360" y2="89" stroke="#c05621" stroke-width="2" stroke-dasharray="5 4"/>
<text x="366" y="93">сборка, нужна сверка</text>
<line x1="540" y1="89" x2="580" y2="89" stroke="#2b6cb0" stroke-width="1.6" stroke-dasharray="4 3"/>
<text x="586" y="93">информация</text>
<polygon points="760,84 774,98 746,98" fill="none" stroke="#243b53"/>
<text x="780" y="93">запас не измерен</text>
</g>'''


def write_value_stream_maps() -> None:
    DIAGRAMS.mkdir(exist_ok=True)
    modes = {
        "kpsc_current.svg": (
            "Текущее состояние. Сборка пульта VENIO-C, первый раунд",
            "Предварительная карта. Секунды — норматив стандарта, не хронометраж.",
            "norm",
        ),
        "kpsc_ideal.svg": (
            "Идеальное состояние. Ориентир, не план смены",
            "Секунды идеального состояния не заданы: замера и подтверждённого решения нет.",
            "ideal",
        ),
        "kpsc_target.svg": (
            "Целевое состояние. Гипотеза H-01, не новый норматив",
            "Меняется только сценарий операции 8: 171 с проверяют как 120 с. Остальные нормы те же.",
            "target",
        ),
    }
    positions = {
        "склад": (24, 250),
        "o1": (230, 130),
        "o3": (230, 300),
        "o5": (230, 470),
        "o6": (230, 640),
        "o2": (460, 130),
        "o4": (700, 230),
        "o7": (940, 360),
        "o8": (1180, 360),
        "o9": (1420, 360),
        "qc": (1660, 360),
        "клиент": (1900, 360),
    }
    for filename, (title, subtitle, mode) in modes.items():
        chunks = [
            '<svg xmlns="http://www.w3.org/2000/svg" width="2140" height="900" viewBox="0 0 2140 900">',
            '<rect width="100%" height="100%" fill="#f8fafc"/>',
            '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L8,3 L0,6 Z" fill="#243b53"/></marker></defs>',
            '<style>text{font-family:sans-serif}</style>',
            _header(title, subtitle),
            _legend(),
        ]
        labels = {
            "склад": ("Склад", ["поставщик комплектов", "рейс: не измерен"]),
            "клиент": ("Клиент", ["забирает по 1 шт.", "заказ: 10 за смену"]),
        }
        for code, name, seconds in OPS:
            if mode == "ideal":
                lines = ["норма есть в стандарте", "ориентир: не выше такта", "значение не задано", "НЗП: не измерено"]
                fill = "#fff"
            elif mode == "target" and code == "o8":
                lines = ["норматив 171 с сохранён", "сценарий: 120 с", "это не новый стандарт", "НЗП: не измерено"]
                fill = "#fff7ed"
            else:
                mark = "выше такта" if seconds > 120 else "не выше такта"
                lines = [f"норматив {seconds} с", mark, "факт: не измерен", "НЗП: не измерено"]
                fill = "#fff5f5" if seconds > 120 else "#fff"
            labels[code] = (name, lines, fill)
        heights = {}
        for key, (x, y) in positions.items():
            item = labels[key]
            fill = item[2] if len(item) == 3 else "#f0f4f8"
            drawing, height = _box(x, y, item[0], item[1], fill=fill)
            chunks.append(drawing)
            heights[key] = height
            chunks.append(f'<polygon points="{x+70},{y+height+8} {x+84},{y+height+24} {x+56},{y+height+24}" fill="none" stroke="#243b53"/>')
            chunks.append(f'<text x="{x+88}" y="{y+height+20}" font-size="10" fill="#627d98">не измерено</text>')
        links = [
            ("склад", "o1"), ("склад", "o2"), ("склад", "o3"), ("склад", "o4"),
            ("склад", "o5"), ("склад", "o6"), ("склад", "o7"), ("склад", "o8"), ("склад", "o9"),
            ("o1", "o2"), ("o2", "o4"), ("o3", "o4"), ("o4", "o7"),
            ("o5", "o7"), ("o6", "o7"), ("o7", "o8"), ("o8", "o9"), ("o9", "qc"), ("qc", "клиент"),
        ]
        confirmed = {("склад", code) for code in ("o1", "o2", "o3", "o4", "o5", "o6", "o7", "o8", "o9")}
        confirmed.add(("qc", "клиент"))
        for left, right in links:
            x1 = positions[left][0] + 168
            y1 = positions[left][1] + 36
            x2 = positions[right][0]
            y2 = positions[right][1] + 36
            dashed = (left, right) not in confirmed and left != "qc"
            color = "#c05621" if dashed else "#243b53"
            chunks.append(_arrow(x1, y1, x2, y2, dashed=dashed, color=color))
        chunks.append(_arrow(1900, 340, 700, 120, dashed=True, color="#2b6cb0"))
        chunks.append('<text x="1100" y="112" font-size="11" fill="#2b6cb0">информация: заказ 10 шт. → начальник производства → склад и стандарты. Факт ОТК отдельно. Деньги бланка-примера не используются.</text>')
        chunks.append("</svg>")
        (DIAGRAMS / filename).write_text("\n".join(chunks), encoding="utf8")


def write_support_diagrams() -> None:
    er = '''<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="620" viewBox="0 0 1100 620">
<style>text{font-family:sans-serif;font-size:13px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="24" y="32" font-size="18" font-weight="700">Данные продукта. Внешней учётной системы нет</text>
<text x="24" y="54" font-size="12" fill="#334e68">Файл data/venio_stage1.sqlite. Те же узлы, что в data/venio_factory.json.</text>
'''
    tables = [
        (40, 80, "process_model", "модель процесса", ["id", "name", "product", "status"]),
        (300, 80, "node", "узел", ["id", "cycle_s", "workers", "cycle_basis"]),
        (560, 80, "material_edge", "материальная связь", ["from_id", "to_id", "verification"]),
        (820, 80, "info_signal", "информационный сигнал", ["from_id", "to_id", "message"]),
        (40, 340, "scenario_settings", "настройка смены", ["shift_s 1200", "takt_s 120", "batch 2"]),
        (300, 340, "scenario_result", "результат сценария", ["accepted", "throughput", "path_s"]),
        (560, 340, "operation_result", "результат операции", ["completed", "utilization", "capacity"]),
        (820, 340, "evidence_reference", "источник", ["subject", "document", "status"]),
    ]
    for x, y, name, ru, fields in tables:
        er += f'<rect x="{x}" y="{y}" width="230" height="{48+18*len(fields)}" fill="#fff" stroke="#1f2933"/>'
        er += f'<text x="{x+10}" y="{y+20}" font-weight="700">{name}</text>'
        er += f'<text x="{x+10}" y="{y+38}" fill="#627d98">{ru}</text>'
        for index, field in enumerate(fields):
            er += f'<text x="{x+10}" y="{y+60+index*18}">{field}</text>'
    er += "</svg>"
    (DIAGRAMS / "er.svg").write_text(er, encoding="utf8")

    state = '''<svg xmlns="http://www.w3.org/2000/svg" width="980" height="220" viewBox="0 0 980 220">
<style>text{font-family:sans-serif;font-size:12px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="16" y="24" font-size="16" font-weight="700">Состояния сессии прототипа</text>'''
    names = ["Нужен вход", "Вошёл", "Модель открыта", "Правка", "Проверка", "Посчитано", "Сравнено"]
    for index, name in enumerate(names):
        x = 16 + index * 136
        state += f'<rect x="{x}" y="70" width="120" height="40" rx="16" fill="#fff" stroke="#1f2933"/>'
        state += f'<text x="{x+10}" y="94">{name}</text>'
        if index:
            state += f'<line x1="{x-16}" y1="90" x2="{x}" y2="90" stroke="#243b53"/>'
    state += '<text x="16" y="150" fill="#334e68">Ошибка ввода возвращает к правке. Выход возвращает к экрану входа. Исходник: analysis/diagrams/state.mmd</text></svg>'
    (DIAGRAMS / "state.svg").write_text(state, encoding="utf8")

    activity = '''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="180" viewBox="0 0 920 180">
<style>text{font-family:sans-serif;font-size:12px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="16" y="24" font-size="16" font-weight="700">Деятельность аналитика</text>
<text x="16" y="70">Открыть модель → проверка → расчёт → выпуск, риск, условный путь</text>
<text x="16" y="98">Если есть гипотеза: меняют параметр только в сценарии → сравнение → разница и оговорка</text>
<text x="16" y="126" fill="#334e68">Исходник: analysis/diagrams/activity.mmd. Норматив текущего состояния при правке не затирается.</text>
</svg>'''
    (DIAGRAMS / "activity.svg").write_text(activity, encoding="utf8")

    sequence = '''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="220" viewBox="0 0 920 220">
<style>text{font-family:sans-serif;font-size:12px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="16" y="24" font-size="16" font-weight="700">Последовательность: браузер и локальный сервер</text>
<text x="16" y="64">Аналитик вводит пароль. Браузер вызывает POST /api/v1/login и получает сессию.</text>
<text x="16" y="90">Запуск расчёта: POST /api/v1/simulate с моделью JSON.</text>
<text x="16" y="116">Сервер проверяет модель. Ошибка — ответ 422 и текст причины. Успех — расчёт движка и JSON.</text>
<text x="16" y="142">На экране дашборд и риск. Внешней учётной системы в цепочке нет.</text>
<text x="16" y="176" fill="#334e68">Исходник: analysis/diagrams/sequence.mmd</text>
</svg>'''
    (DIAGRAMS / "sequence.svg").write_text(sequence, encoding="utf8")

    architecture = '''<svg xmlns="http://www.w3.org/2000/svg" width="980" height="220" viewBox="0 0 980 220">
<style>text{font-family:sans-serif;font-size:12px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="16" y="24" font-size="16" font-weight="700">Состав прототипа</text>
<text x="16" y="64">Браузер frontend → локальный Python API → проверка модели → движок backend/engine.py</text>
<text x="16" y="90">Демо-модель: data/venio_factory.json. Таблицы защиты: data/venio_stage1.sqlite</text>
<text x="16" y="116">1С, ERP и MES не подключены. 3D-тур не входит в этот этап.</text>
<text x="16" y="150" fill="#334e68">Исходник схемы компонентов: analysis/diagrams/architecture.mmd</text>
</svg>'''
    (DIAGRAMS / "architecture.svg").write_text(architecture, encoding="utf8")

    usecase = '''<svg xmlns="http://www.w3.org/2000/svg" width="980" height="250" viewBox="0 0 980 250">
<style>text{font-family:sans-serif;font-size:13px;fill:#102a43}</style>
<rect width="100%" height="100%" fill="#f8fafc"/>
<text x="16" y="28" font-size="16" font-weight="700">Варианты использования</text>
<text x="16" y="64">Начальник производства: запустить модель, сравнить два сценария, увидеть риск операции 8.</text>
<text x="16" y="90">Аналитик: войти, открыть карту, править только сценарий, импортировать и экспортировать JSON.</text>
<text x="16" y="116">Менеджер по труду: экран денег пуст, пока ставки не введены. Учебные рубли бланка не подставлять.</text>
<text x="16" y="142">Логист: на карте партия 2 штуки, время рейса не измерено.</text>
<text x="16" y="168">Контролёр ОТК: контрольная операция, норматив 22 с, факт брака не измерен.</text>
<text x="16" y="210" fill="#334e68">Отдельных учётных записей этих ролей в прототипе нет. Роли — роли смены из общего описания.</text>
</svg>'''
    (DIAGRAMS / "use_case.svg").write_text(usecase, encoding="utf8")


def main() -> None:
    build_database()
    write_value_stream_maps()
    write_support_diagrams()


if __name__ == "__main__":
    main()
