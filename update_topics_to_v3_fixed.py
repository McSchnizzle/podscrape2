"""
Update all topics to use eleven_v3 model via direct SQL.
"""
from src.database.models import get_database_manager
from sqlalchemy import text

db = get_database_manager()

with db.get_session() as session:
    # Update all topics to eleven_v3
    result = session.execute(text("""
        UPDATE topics
        SET dialogue_model = 'eleven_v3'
        WHERE dialogue_model != 'eleven_v3'
    """))

    print(f"Updated {result.rowcount} topics to eleven_v3")

    # Verify
    topics = session.execute(text("SELECT name, dialogue_model, use_dialogue_api FROM topics")).fetchall()
    print("\nCurrent topic settings:")
    for name, model, use_dialogue in topics:
        mode = "dialogue (2 voices)" if use_dialogue else "single voice"
        print(f"  {name}: {model} ({mode})")

    session.commit()
    print("\n✅ Database updated successfully")
