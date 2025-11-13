"""
Update all topics to use eleven_v3 model.
- Social Movements: Keep dialogue mode (2 voices)
- AI and Tech: Single voice narrative with v3
- Psychedelics: Single voice narrative with v3
"""
from src.database.models import get_topic_repo

repo = get_topic_repo()
topics = repo.get_all_topics()

for topic in topics:
    print(f"\n{topic.name}:")
    print(f"  Current model: {topic.dialogue_model}")
    print(f"  Dialogue mode: {topic.use_dialogue_api}")

    # Update to eleven_v3
    topic.dialogue_model = "eleven_v3"

    # Only Social Movements uses dialogue mode (2 voices)
    if "Community" in topic.name:
        topic.use_dialogue_api = True
        print(f"  → eleven_v3 (dialogue mode - 2 voices)")
    else:
        topic.use_dialogue_api = False
        print(f"  → eleven_v3 (single voice with audio tags)")

# Save changes
print("\nSaving changes to database...")
repo.session.commit()
print("✅ All topics updated to eleven_v3")
