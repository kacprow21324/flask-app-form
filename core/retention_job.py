from app import DATA_DIR, app
from core.retention import process_due_archives


def run():
    with app.app_context():
        processed = process_due_archives(base_dir=DATA_DIR)
        print(f"Anonimizacja zakończona: processed={len(processed)}")


if __name__ == "__main__":
    run()
