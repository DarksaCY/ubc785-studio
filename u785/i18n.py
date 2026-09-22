"""Minimal i18n: English is the source language, Russian is a lookup table.

Usage: _("Read {ok} of {total}", ok=3, total=5). The language is chosen once at
startup (before UI modules are imported, since some labels are module-level).
"""
LANGUAGES = {"en": "English", "ru": "Русский"}
_lang = "en"


def set_language(code: str):
    global _lang
    _lang = code if code in LANGUAGES else "en"


def language() -> str:
    return _lang


def _(text: str, /, **kw) -> str:
    if _lang == "ru":
        text = RU.get(text, text)
    return text.format(**kw) if kw else text


RU = {
    # --- core --------------------------------------------------------------
    "Not a frequency: {text}": "Не похоже на частоту: {text}",
    "Unknown unit: {unit}": "Неизвестная единица: {unit}",
    "{f} MHz is outside 25–1300 MHz": "{f} МГц вне диапазона 25–1300 МГц",
    "Unknown tone: {text}": "Неизвестный тон: {text}",
    "Unknown DCS code: {text}": "Неизвестный DCS код: {text}",
    "Unknown CTCSS tone: {text}": "Неизвестный CTCSS тон: {text}",
    "{cmd}: no response": "{cmd}: нет ответа",
    "No response to {cmd}": "Нет ответа на {cmd}",
    "Channel {n}: the scanner rejected the frequency ({r})": "Канал {n}: сканер отклонил частоту ({r})",
    "The scanner rejected the frequency ({r})": "Сканер не принял частоту ({r})",
    "Unexpected PM{n:03d} reply: {resp}": "Непонятный ответ PM{n:03d}: {resp}",
    "File is empty": "Файл пуст",
    "Line {n}: {msg}": "Строка {n}: {msg}",
    "Line {n}: channel number {value} not recognized": "Строка {n}: номер канала {value} не распознан",
    "Line {n}: channel {ch} outside 1–{max}": "Строка {n}: канал {ch} вне 1–{max}",
    "Line {n}: modulation {mod} replaced with AUTO": "Строка {n}: модуляция {mod} заменена на AUTO",
    # --- worker ------------------------------------------------------------
    "The scanner did not answer SI — check the port speed": "Сканер не ответил на SI — проверьте скорость порта",
    "Scanner not connected": "Сканер не подключён",
    "The scanner stopped responding": "Сканер перестал отвечать",
    "Reading channel {n:03d}": "Чтение канала {n:03d}",
    "Read {ok} of {total} in {secs:.0f} s": "Прочитано {ok} из {total} за {secs:.0f} с",
    "; errors: {list}": "; ошибки: {list}",
    "Cancelled. ": "Отменено. ",
    "Writing channel {n:03d}": "Запись канала {n:03d}",
    "Wrote {ok} of {total}": "Записано {ok} из {total}",
    "; not written: {list}": "; не записаны: {list}",
    "Bank {b}": "Банк {b}",
    "Banks read": "Банки прочитаны",
    "Banks written": "Банки записаны",
    "The USB-serial driver could not configure the port (typical of CH340 clones). "
    "Replug the cable and try again.":
        "Драйвер USB-COM не смог настроить порт (типично для клонов CH340). "
        "Переподключите кабель и попробуйте снова.",
    "The port is in use by another program.": "Порт занят другой программой.",
    "Port not found. Check the cable.": "Порт не найден. Проверьте кабель.",
    # --- widgets -----------------------------------------------------------
    "NO LINK TO SCANNER": "НЕТ СВЯЗИ СО СКАНЕРОМ",
    "● OPEN": "● ОТКР",
    "○ CLOSED": "○ ЗАКР",
    "Formats: 145.5  145,500  145.500.000  145500k  145.5 MHz  1.2975G":
        "Форматы: 145.5  145,500  145.500.000  145500k  145.5 MHz  1.2975G",
    "= {f} MHz   ⏎ tune": "= {f} МГц   ⏎ настроить",
    # --- channel table -----------------------------------------------------
    "BANK": "БАНК",
    "FREQ, MHz": "ЧАСТОТА, МГц",
    "MOD": "МОД",
    "TAG": "МЕТКА",
    "TONE": "ТОН",
    "On the scanner display: “{text}”": "На дисплее сканера: «{text}»",
    "Modified — not yet written to the scanner": "Изменено — ещё не записано в сканер",
    "Unknown modulation {value}": "Неизвестная модуляция {value}",
    "tag (16 chars)": "метка (16 симв.)",
    "Cleared {n} channel(s) (remember to write)": "Очищено каналов: {n} (не забудьте записать)",
    "Copied {n} channel(s)": "Скопировано каналов: {n}",
    "Pasted {n} channel(s) starting at {start:03d}": "Вставлено каналов: {n}, начиная с {start:03d}",
    " — {n} warning(s)": " — предупреждений: {n}",
    # --- import dialog -----------------------------------------------------
    "Import CSV": "Импорт CSV",
    "Frequencies found: {n}": "Найдено частот: {n}",
    " · file has channel numbers": " · номера каналов есть в файле",
    "FREQUENCY": "ЧАСТОТА",
    "Place into:": "Куда поместить:",
    "By channel numbers from the file": "По номерам каналов из файла",
    "Sequentially, starting at channel": "Подряд, начиная с канала",
    "Into free channels of bank": "В свободные каналы банка",
    "Skip frequencies already in memory": "Пропускать частоты, которые уже есть в памяти",
    "Warnings ({n}):": "Предупреждения ({n}):",
    "Import": "Импортировать",
    "Cancel": "Отмена",
    "Channels to fill: {n}": "Будет заполнено каналов: {n}",
    " · overwrites occupied: {n}": " · перезапишет занятых: {n}",
    " · skipped: {n}": " · пропущено: {n}",
    # --- main window -------------------------------------------------------
    "{v} kHz": "{v} кГц",
    "Refresh port list": "Обновить список портов",
    "Connect": "Подключить",
    "Disconnect": "Отключить",
    "Connecting…": "Подключение…",
    "PORT": "ПОРТ",
    "BAUD": "БОД",
    "MODE": "РЕЖИМ",
    "LANG": "ЯЗЫК",
    "not connected": "не подключено",
    "Scanner display": "Дисплей сканера",
    "MHz": "МГц",
    "Controls": "Управление",
    "Direct tuning (VFO)": "Прямая настройка (VFO)",
    "Step down (Ctrl+↓)": "Шаг вниз (Ctrl+↓)",
    "Step up (Ctrl+↑)": "Шаг вверх (Ctrl+↑)",
    "Tune": "Настроить",
    "Functions": "Функции",
    "Priority channel": "Приоритетный канал",
    "Delay (current channel)": "Задержка (текущий канал)",
    "Attenuator (current channel)": "Аттенюатор (текущий канал)",
    "Key beep": "Звук клавиш",
    "BACKLIGHT": "ПОДСВЕТКА",
    "On": "Вкл",
    "Dim": "Тускл",
    "Off": "Выкл",
    "AUDIO": "ЗВУК",
    "Auto": "Авто",
    "Open": "Открыт",
    "Mute": "Тихо",
    "Channels": "Каналы",
    "Banks": "Банки",
    "Console": "Консоль",
    "↓ Read from scanner": "↓ Прочитать из сканера",
    "Entire memory (1–500)": "Всю память (1–500)",
    "Current bank": "Текущий банк",
    "Selected channels": "Выделенные каналы",
    "↑ Write changes": "↑ Записать изменения",
    "Revert edits": "Отменить правки",
    "Read modulation": "Читать модуляцию",
    "Modulation is not part of the PM reply: to read it the scanner\n"
    "switches to each channel (MA + RM). Reading takes longer.":
        "Модуляция не входит в ответ PM: для её чтения сканер\n"
        "переключается на каждый канал (MA + RM). Чтение дольше.",
    "Export CSV": "Экспорт CSV",
    "All programmed channels": "Все заполненные каналы",
    "Visible only (filter)": "Только видимые (фильтр)",
    "Selected only": "Только выделенные",
    "Full memory image (incl. empty)": "Полный образ памяти (с пустыми)",
    "ALL": "ВСЕ",
    "Search: frequency, tag, number…   (Ctrl+F)": "Поиск: частота, метка, номер…   (Ctrl+F)",
    "Hide empty": "Скрыть пустые",
    "Double-click a number to jump to that channel on the scanner · Del — clear · "
    "Ctrl+C / Ctrl+V — copy and paste rows (works with Excel too)":
        "Двойной клик по номеру — перейти на канал в сканере · Del — очистить · "
        "Ctrl+C / Ctrl+V — копировать и вставлять строки (в т. ч. из Excel)",
    "↓ Read banks": "↓ Прочитать банки",
    "↑ Write banks": "↑ Записать банки",
    "CHANNELS": "КАНАЛЫ",
    "BANK TAG": "МЕТКА БАНКА",
    "IN SCAN": "СКАНИРОВАТЬ",
    "SEARCH: LOW": "ПОИСК: НИЗ",
    "SEARCH: HIGH": "ПОИСК: ВЕРХ",
    "Bank tags appear on the scanner display (up to 16 characters, Cyrillic is "
    "transliterated). “Scan” selects which banks take part in scanning.":
        "Метки банков видны на дисплее сканера (до 16 символов, кириллица "
        "транслитерируется). «Сканировать» — какие банки участвуют в сканировании.",
    "Protocol command, e.g. PM001, TA C 001, SG, KEY00 …":
        "Команда протокола, например: PM001, TA C 001, SG, KEY00 …",
    "Send": "Отправить",
    "Show polling": "Показывать опрос",
    "Clear": "Очистить",
    "Stop": "Стоп",
    " · firmware {fw}": " · прошивка {fw}",
    "Scanner connected": "Сканер подключён",
    "Enter a frequency between 25 and 1300 MHz": "Введите частоту в диапазоне 25–1300 МГц",
    "Tuning to {f} MHz {mod}": "Настройка на {f} МГц {mod}",
    "There are unwritten changes. Reading will replace them with data from the scanner. Continue?":
        "Есть незаписанные изменения. При чтении они будут заменены данными из сканера. Продолжить?",
    "Choose a bank with the A–J buttons above the table": "Выберите банк кнопками A–J над таблицей",
    "Write {n} changed channel(s) to the scanner?": "Записать в сканер изменённые каналы: {n}?",
    "{n} of them will be erased.": "Из них будут стёрты: {n}.",
    "While writing, the scanner switches to manual mode and then returns to SCAN.":
        "Во время записи сканер перейдёт в ручной режим, затем вернётся в SCAN.",
    "At least one bank must be included in scanning": "Хотя бы один банк должен участвовать в сканировании",
    "Go to channel {n:03d} on the scanner": "Перейти на канал {n:03d} в сканере",
    "Read from scanner ({n})": "Прочитать из сканера ({n})",
    "Copy  Ctrl+C": "Копировать  Ctrl+C",
    "Paste  Ctrl+V": "Вставить  Ctrl+V",
    "Clear ({n})  Del": "Очистить ({n})  Del",
    "CSV (*.csv *.txt);;All files (*)": "CSV (*.csv *.txt);;Все файлы (*)",
    "Could not read the file:\n{e}": "Не удалось прочитать файл:\n{e}",
    "No frequencies found in the file.": "В файле не найдено частот.",
    "Imported {n} channel(s) — review them and press “Write changes”":
        "Импортировано каналов: {n} — проверьте и нажмите «Записать изменения»",
    "Saved {n} channel(s) → {path}": "Сохранено каналов: {n} → {path}",
    "● modified: {n}": "● изменено: {n}",
    "There are unwritten changes. Quit without writing?": "Есть незаписанные изменения. Выйти без записи?",
    "Restart the app now to switch the language?": "Перезапустить приложение сейчас, чтобы сменить язык?",
    "Full screen (F11 / Alt+Enter)": "Полный экран (F11 / Alt+Enter)",
}
