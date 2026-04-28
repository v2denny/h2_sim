import csv
import os


class Logger:
    def __init__(self, filename: str):
        self.filename = filename

    def log(self, row: dict):
        file_exists = os.path.exists(self.filename)

        with open(self.filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=row.keys())

            if not file_exists:
                writer.writeheader()

            writer.writerow(row)