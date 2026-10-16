import os
import shutil
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from pymongo import MongoClient


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
LOCAL_STORAGE_DIR = PROJECT_ROOT / "data" / "raw"


def save_file_locally(file_path, file_name=None):
    """Salin dokumen ke data/raw dan kembalikan path hasil salinan."""
    source_path = Path(file_path)
    if not source_path.is_file():
        raise FileNotFoundError(f"File sumber tidak ditemukan: {source_path}")

    # Hanya gunakan nama file, sehingga file_name tidak dapat menunjuk ke luar
    # direktori penyimpanan lokal.
    destination_name = Path(file_name or source_path.name).name
    LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    destination_path = LOCAL_STORAGE_DIR / destination_name

    if source_path.resolve() != destination_path.resolve():
        shutil.copy2(source_path, destination_path)

    return str(destination_path)


def _required_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Variabel {name} belum diatur di file .env.")
    return value


def load_to_mongo(document_data):
    """Simpan satu dokumen metadata hasil ekstraksi ke MongoDB."""
    mongo_uri = _required_env("MONGO_URI")
    database_name = _required_env("MONGO_DB")
    collection_name = _required_env("MONGO_COLLECTION")

    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        collection = client[database_name][collection_name]
        result = collection.insert_one(document_data)
        return str(result.inserted_id)


def load_to_postgres(file_name, entities):
    """Simpan nama file dan entitas hasil ekstraksi ke PostgreSQL."""
    connection = psycopg2.connect(
        dbname=_required_env("POSTGRES_DB"),
        user=_required_env("POSTGRES_USER"),
        password=_required_env("POSTGRES_PASS"),
        host=_required_env("POSTGRES_HOST"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
    )

    try:
        with connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO extracted_entities
                        (file_name, extracted_name, invoice_date, total_price)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (
                        file_name,
                        entities.get("name"),
                        entities.get("date"),
                        entities.get("total_price"),
                    ),
                )
    finally:
        connection.close()
