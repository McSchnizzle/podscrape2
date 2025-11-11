#!/usr/bin/env python3
"""
Quick test script for dialogue_chunker module.
Tests chunking logic with sample dialogue script.
"""

from src.audio.dialogue_chunker import chunk_dialogue_script

# Sample dialogue script (simulating a 20k character script with audio tags)
SAMPLE_DIALOGUE = """
SPEAKER_1: [excited] Hey everyone! Welcome back to the Community Organizing Digest. I'm so pumped to share what's happening in movements across the country today. Have you been following the latest developments in labor organizing?

SPEAKER_2: [thoughtful] Absolutely! And it's fascinating to see how traditional organizing tactics are being reimagined for the digital age. But before we dive in, let's set the stage for our listeners who might be new to these concepts.

SPEAKER_1: [warm] Great idea! So, community organizing at its core is about bringing people together around shared concerns and building power to create change. What makes it so powerful is that it's bottom-up, driven by the community itself.

SPEAKER_2: [engaged] Exactly. And what we're seeing now is a real renaissance in grassroots organizing. From tenant unions to mutual aid networks, people are rediscovering the power of collective action. Let's talk about some specific examples.

SPEAKER_1: [enthusiastic] Yes! One of the most exciting developments is happening in the labor movement. Workers at companies like Amazon and Starbucks are organizing at unprecedented rates. What's different this time is the way they're using social media to coordinate and build solidarity.

SPEAKER_2: [analytical] That's such a crucial point. The traditional model of union organizing often relied on in-person meetings and door-knocking campaigns. While those are still important, organizers are now combining them with digital tools to reach workers more effectively.

SPEAKER_1: [inspired] And it's not just about unions. We're seeing neighborhood associations tackle housing affordability, environmental justice groups fight pollution in their communities, and parents organize for better schools. The common thread is people taking collective action.

SPEAKER_2: [reflective] What strikes me most is how these movements are building real power. It's not just about protest or awareness - though those are important. It's about creating organizations that can negotiate, apply pressure, and win concrete victories for their members.

SPEAKER_1: [determined] Absolutely. And that's why we need to pay attention to the strategies they're using. Things like one-on-one conversations to build relationships, identifying and developing leaders from within the community, and running campaigns with clear, winnable goals.

SPEAKER_2: [hopeful] The future of organizing looks bright, especially as younger generations bring fresh energy and new perspectives to this work. They're not just inheriting old models - they're innovating and creating hybrid approaches that combine the best of traditional organizing with modern tools.

SPEAKER_1: [concluding] That's it for today's overview. In our next segment, we'll dive deeper into specific campaigns and what we can learn from them. Thanks for listening!

SPEAKER_2: [warm] See you next time!
""" * 5  # Multiply to create a larger script for chunking test


def test_chunking():
    """Test dialogue chunking with sample script"""
    print("=" * 60)
    print("Testing Dialogue Chunker")
    print("=" * 60)

    script_length = len(SAMPLE_DIALOGUE)
    print(f"\nSample script length: {script_length:,} characters")
    print(f"Max chunk size: 2,800 characters")
    print(f"Expected chunks: ~{script_length // 2800} chunks\n")

    try:
        # Test chunking
        chunks = chunk_dialogue_script(SAMPLE_DIALOGUE, max_chunk_size=2800)

        print(f"✅ Successfully chunked script into {len(chunks)} chunks\n")

        # Display chunk details
        for chunk in chunks:
            print(f"Chunk {chunk.chunk_number}:")
            print(f"  Characters: {chunk.char_count}")
            print(f"  Turns: {chunk.turn_count}")
            print(f"  Speakers: {', '.join(chunk.speakers)}")

            # Verify chunk is within limit
            if chunk.char_count > 2800:
                print(f"  ⚠️  WARNING: Chunk exceeds limit!")
            else:
                print(f"  ✅ Within limit")

            # Show first 100 chars as preview
            preview = chunk.text[:100].replace('\n', ' ')
            print(f"  Preview: {preview}...\n")

        # Summary
        print("=" * 60)
        print("Summary:")
        print(f"  Total chunks: {len(chunks)}")
        print(f"  Total characters: {sum(c.char_count for c in chunks):,}")
        print(f"  Average chunk size: {sum(c.char_count for c in chunks) // len(chunks):,} chars")
        print(f"  Largest chunk: {max(c.char_count for c in chunks):,} chars")
        print(f"  Smallest chunk: {min(c.char_count for c in chunks):,} chars")
        print("=" * 60)

        # Verify all chunks are within limit
        oversized = [c for c in chunks if c.char_count > 2800]
        if oversized:
            print(f"\n⚠️  {len(oversized)} chunk(s) exceed the 2,800 character limit")
            return False
        else:
            print("\n✅ All chunks are within the character limit!")
            return True

    except Exception as e:
        print(f"\n❌ Error during chunking: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_chunking()
    exit(0 if success else 1)
