from app import app
from flask_migrate import upgrade

from core.backfill import backfill_approved_revisions, backfill_operational_data


def run():
    with app.app_context():
        upgrade()
        created = backfill_operational_data()
        approved_revisions = backfill_approved_revisions()
        print(
            "Migracja zakończona: "
            + ", ".join(f"{name}=+{count}" for name, count in created.items())
            + f", approved_revisions=+{approved_revisions}"
        )


if __name__ == "__main__":
    run()
