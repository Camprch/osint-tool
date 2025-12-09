import csv
from app.database import get_session
from app.models.message import Message

OUTPUT_FILE = "messages_export.csv"

with get_session() as session:
    messages = session.query(Message).all()

with open(OUTPUT_FILE, "w", newline='', encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "raw_text", "translated_text"])
    for m in messages:
        writer.writerow([
            m.id,
            m.raw_text.replace('\n', ' ') if m.raw_text else '',
            m.translated_text.replace('\n', ' ') if m.translated_text else ''
        ])

print(f"Exporté {len(messages)} messages dans {OUTPUT_FILE}")
