import requests
import xml.etree.ElementTree as ET
import sqlite3
from datetime import datetime

# 1. EXTRACT (Извлечение данных с официального фида Нацбанка РК)
# 1. EXTRACT (Извлечение данных с заголовком браузера)

# domain = "https://nationalbank.kz"
# path = "rss"
# filename = "rates" + "_" + "all.xml"

# url = f"{domain}/{path}/{filename}"


url = "https://nationalbank.kz/rss/rates_all.xml"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
}

response = requests.get(url, headers=headers)
response.raise_for_status()

# Проверяем, что пришел действительно XML, а не HTML-заглушка
if not response.text.strip().startswith("<?xml"):
    print("Ошибка: сервер вернул не XML. Начало ответа:")
    print(response.text[:300])
    exit()

# 2. TRANSFORM (Разбор XML, извлечение даты курса и очистка данных)
root = ET.fromstring(response.content)
target_currencies = ["USD", "EUR", "RUB"]
cleaned_data = []
loaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for item in root.findall(".//item"):
    code = item.find("title").text.strip()
    if code in target_currencies:
        rate = float(item.find("description").text.strip())
        quant = int(item.find("quant").text.strip())
        actual_rate = round(rate / quant, 4)

        # Забираем официальную дату курса из XML (формат на сайте: ДД.ММ.ГГГГ)
        raw_date = item.find("pubDate").text.strip()
        # Переводим дату в стандартный для баз данных формат ГГГГ-ММ-ДД
        rate_date = datetime.strptime(
            raw_date, "%d.%m.%Y").strftime("%Y-%m-%d")

        cleaned_data.append((rate_date, code, actual_rate, loaded_at))

# 3. LOAD (Идемпотентная загрузка в SQLite без дублей)
conn = sqlite3.connect("nbk_rates.db")
cursor = conn.cursor()

# Создаем таблицу с жестким правилом уникальности для пары (rate_date, currency)
cursor.execute("""
    CREATE TABLE IF NOT EXISTS exchange_rates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        rate_date TEXT,
        currency TEXT,
        rate_kzt REAL,
        loaded_at TEXT,
        UNIQUE(rate_date, currency)
    )
""")

# Используем INSERT OR IGNORE: если дата и валюта уже есть, строка просто пропускается
cursor.executemany(
    """
    INSERT OR IGNORE INTO exchange_rates (rate_date, currency, rate_kzt, loaded_at) 
    VALUES (?, ?, ?, ?)
    """,
    cleaned_data
)

# Проверяем, сколько реально новых строк добавилось
added_rows = cursor.rowcount

conn.commit()
conn.close()

if added_rows > 0:
    print(f"Успешно добавлено новых записей: {added_rows}")
else:
    print("Новых курсов нет. Дубликаты пропущены.")
