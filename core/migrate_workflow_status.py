from app import app
from core.workflow_migration import remove_mongo_workflow_metadata


def run():
    with app.app_context():
        result = remove_mongo_workflow_metadata()
        print(
            "Migracja statusów zakończona: "
            f"utworzone={result['created']}, "
            f"oczyszczone={result['cleaned']}, "
            f"pozostałe={result['remaining']}"
        )


if __name__ == "__main__":
    run()
