"""
Dialogue Script Chunking for ElevenLabs Text-to-Dialogue API.

Splits multi-voice dialogue scripts into chunks that fit within the v3 model's
character limit while preserving dialogue boundaries and speaker continuity.
"""

import re
import logging
from typing import List, Dict, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DialogueChunk:
    """Metadata for a dialogue script chunk"""
    chunk_number: int
    text: str
    char_count: int
    speakers: List[str]
    turn_count: int

class DialogueChunker:
    """
    Chunks dialogue scripts for ElevenLabs Text-to-Dialogue API.

    Ensures chunks:
    - Never exceed max character limit (default: 2,800 chars for v3's 3,000 limit)
    - Never split mid-speaker-turn
    - Preserve speaker labels and audio tags
    - Maintain dialogue flow across chunks
    """

    # Regex to match speaker turns: SPEAKER_1: or SPEAKER_2: or SPEAKER_1 (Name): or SPEAKER_1 [Name, emotion]:
    # Matches: "SPEAKER_1:", "SPEAKER_2:", "SPEAKER_1 (Young Jamal):", "SPEAKER_1 [Jamal, excited]:", etc.
    SPEAKER_PATTERN = re.compile(r'^(SPEAKER_[12])(?:\s*[\(\[][^\)\]]+[\)\]])?:\s*', re.MULTILINE)

    def __init__(self, max_chunk_size: int = 2800):
        """
        Initialize chunker with character limit.

        Args:
            max_chunk_size: Maximum characters per chunk (default: 2,800 for safety margin)
        """
        self.max_chunk_size = max_chunk_size

    def chunk_dialogue_script(self, script: str) -> List[DialogueChunk]:
        """
        Split dialogue script into chunks at speaker boundaries.

        Args:
            script: Full dialogue script with SPEAKER_1/SPEAKER_2 labels

        Returns:
            List of DialogueChunk objects with metadata

        Raises:
            ValueError: If script is empty or has no speaker labels
        """
        if not script or not script.strip():
            raise ValueError("Script is empty")

        # Parse script into individual speaker turns
        turns = self._parse_speaker_turns(script)

        if not turns:
            raise ValueError("No speaker turns found in script (expected SPEAKER_1: or SPEAKER_2: labels)")

        logger.info(f"Parsed {len(turns)} speaker turns from script ({len(script)} chars)")

        # Pre-split any oversized turns before chunking
        turns = self._normalize_turn_sizes(turns)
        logger.info(f"Normalized to {len(turns)} turns (after splitting oversized turns)")

        # Group turns into chunks that fit within character limit
        chunks = self._create_chunks(turns)

        logger.info(f"Created {len(chunks)} chunks from dialogue script")

        return chunks

    def _parse_speaker_turns(self, script: str) -> List[Dict[str, str]]:
        """
        Parse script into individual speaker turns.

        Returns:
            List of dicts with 'speaker' and 'text' keys
        """
        turns = []

        # Split script by speaker labels
        parts = self.SPEAKER_PATTERN.split(script)

        # parts will be: ['', 'SPEAKER_1', 'text1', 'SPEAKER_2', 'text2', ...]
        # We need to pair speakers with their text
        for i in range(1, len(parts), 2):
            if i + 1 < len(parts):
                speaker = parts[i]
                text = parts[i + 1].strip()

                if text:  # Skip empty turns
                    turns.append({
                        'speaker': speaker,
                        'text': text
                    })

        return turns

    def _normalize_turn_sizes(self, turns: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """
        Pre-split any turns that exceed max_chunk_size.
        This ensures _create_chunks never encounters oversized turns.

        Args:
            turns: List of parsed speaker turns

        Returns:
            List of normalized turns, all within max_chunk_size
        """
        normalized_turns = []

        for turn in turns:
            # Reconstruct turn with speaker label to get full size
            turn_text = f"{turn['speaker']}: {turn['text']}"
            turn_size = len(turn_text)

            if turn_size > self.max_chunk_size:
                # Split this oversized turn
                sub_turns = self._split_long_turn(turn, self.max_chunk_size)
                normalized_turns.extend(sub_turns)
            else:
                # Turn is fine as-is
                normalized_turns.append(turn)

        return normalized_turns

    def _split_long_turn(self, turn: Dict[str, str], max_size: int) -> List[Dict[str, str]]:
        """
        Split a long turn at sentence boundaries to fit within max_size.

        Args:
            turn: Turn dict with 'speaker' and 'text' keys
            max_size: Maximum characters including speaker label

        Returns:
            List of turn dicts, each within max_size
        """
        speaker = turn['speaker']
        text = turn['text']

        # Account for speaker label in size
        label_overhead = len(f"{speaker}: ")
        max_text_size = max_size - label_overhead

        # Split into sentences
        import re
        sentences = re.split(r'([.!?]+\s+)', text)

        sub_turns = []
        current_text = ""

        for i in range(0, len(sentences), 2):
            sentence = sentences[i]
            punctuation = sentences[i + 1] if i + 1 < len(sentences) else ""
            full_sentence = sentence + punctuation

            if len(current_text) + len(full_sentence) > max_text_size and current_text:
                # Save current sub-turn and start new one
                sub_turns.append({'speaker': speaker, 'text': current_text.strip()})
                current_text = full_sentence
            else:
                current_text += full_sentence

        # Add final sub-turn
        if current_text.strip():
            sub_turns.append({'speaker': speaker, 'text': current_text.strip()})

        logger.info(f"Split long turn into {len(sub_turns)} sub-turns at sentence boundaries")
        return sub_turns

    def _create_chunks(self, turns: List[Dict[str, str]]) -> List[DialogueChunk]:
        """
        Group speaker turns into chunks that fit within character limit.

        All turns are already normalized (pre-split), so we just need to group them.

        Strategy:
        - Add turns to current chunk until adding next turn would exceed limit
        - Start new chunk at turn boundary
        """
        chunks = []
        current_chunk_turns = []
        current_chunk_size = 0

        for turn in turns:
            # Reconstruct turn text with speaker label
            turn_text = f"{turn['speaker']}: {turn['text']}"
            turn_size = len(turn_text)

            # All turns should be pre-normalized, but verify
            if turn_size > self.max_chunk_size:
                raise ValueError(
                    f"Turn ({turn_size} chars) exceeds chunk limit ({self.max_chunk_size} chars). "
                    f"This should never happen after normalization."
                )

            # Check if adding this turn would exceed limit
            # (Add 1 for newline between turns)
            potential_size = current_chunk_size + turn_size + (1 if current_chunk_turns else 0)

            if potential_size > self.max_chunk_size and current_chunk_turns:
                # Save current chunk and start new one
                chunks.append(self._finalize_chunk(current_chunk_turns, len(chunks) + 1))
                current_chunk_turns = []
                current_chunk_size = 0

            # Add turn to current chunk
            current_chunk_turns.append(turn)
            current_chunk_size += turn_size + (1 if len(current_chunk_turns) > 1 else 0)

        # Add final chunk
        if current_chunk_turns:
            chunks.append(self._finalize_chunk(current_chunk_turns, len(chunks) + 1))

        return chunks

    def _finalize_chunk(self, turns: List[Dict[str, str]], chunk_number: int) -> DialogueChunk:
        """
        Convert list of turns into a DialogueChunk with metadata.
        """
        # Reconstruct chunk text with speaker labels
        chunk_lines = []
        speakers = set()

        for turn in turns:
            chunk_lines.append(f"{turn['speaker']}: {turn['text']}")
            speakers.add(turn['speaker'])

        chunk_text = '\n'.join(chunk_lines)

        return DialogueChunk(
            chunk_number=chunk_number,
            text=chunk_text,
            char_count=len(chunk_text),
            speakers=sorted(list(speakers)),
            turn_count=len(turns)
        )


def chunk_dialogue_script(script: str, max_chunk_size: int = 2800) -> List[DialogueChunk]:
    """
    Convenience function to chunk a dialogue script.

    Args:
        script: Full dialogue script with SPEAKER_1/SPEAKER_2 labels
        max_chunk_size: Maximum characters per chunk (default: 2,800)

    Returns:
        List of DialogueChunk objects
    """
    chunker = DialogueChunker(max_chunk_size=max_chunk_size)
    return chunker.chunk_dialogue_script(script)
