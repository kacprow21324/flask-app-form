from app import app
from flask_migrate import upgrade

from core.backfill import backfill_operational_data


def run():
    with app.app_context():
        upgrade()
        created = backfill_operational_data()
        print(
            "Migracja zakończona: "
            + ", ".join(f"{name}=+{count}" for name, count in created.items())
        )


if __name__ == "__main__":
    run()
