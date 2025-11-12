# Episode 364 Timeout Issue

## Summary
Social Movements digest ID 364 (timestamp 05:34:47) repeatedly times out during Text-to-Dialogue API generation.

## Details

**Digest Information:**
- Database ID: 364
- Topic: Social Movements and Community Organizing
- Date: 2025-11-10
- Timestamp: 2025-11-11 05:34:47.123737
- Script length: 26,935 characters
- Expected chunks: ~10 dialogue chunks (at 2800 chars each)

**Issue:**
The ElevenLabs Text-to-Dialogue API calls are timing out during chunk generation. The script ran for 19+ minutes before being killed, showing repeated timeout messages:

```
Text-to-Dialogue request timed out (attempt 1/4), retrying...
Text-to-Dialogue request timed out (attempt 1/4), retrying...
```

## Hypotheses

### 1. Script Size Too Large
- **Evidence**: This is the longest Social Movements script at 26,935 chars
- **Theory**: 10+ dialogue chunks may be hitting ElevenLabs API rate limits or internal processing limits
- **Comparison**: Successfully regenerated episode 362 (21,495 chars = ~8 chunks) and episode 360 (not documented but smaller)

### 2. ElevenLabs API Rate Limiting
- **Evidence**: Multiple consecutive Text-to-Dialogue API calls in sequence
- **Theory**: Rapid fire API calls for 10 chunks may trigger rate limiting
- **Solution**: Add delay between chunk generation calls

### 3. Complex Speaker Label Format
- **Evidence**: Script uses `SPEAKER_1 [Jamal, excited]:` format with emotions in brackets
- **Theory**: v3 Text-to-Dialogue API may struggle with parsing/processing these complex labels
- **Note**: We fixed the regex to parse these correctly, but API itself might have issues

### 4. API Timeout Configuration
- **Evidence**: Current timeout is 120 seconds per chunk (audio_generator.py line 277)
- **Theory**: Large dialogue chunks may legitimately take longer than 120s to generate
- **Solution**: Increase timeout for Text-to-Dialogue API calls specifically

## Successful Episodes (For Comparison)

**Social Movements:**
- ID 360: 21,495 chars - ✅ Generated successfully
- ID 362: Unknown size - ✅ Generated successfully (was already good)

**AI and Technology (with narrative chunking):**
- ID 353: 10,270 chars - ✅ Generated successfully
- ID 356: 20,658 chars - ✅ Generated successfully
- ID 359: 18,673 chars - ✅ Generated successfully
- ID 361: 24,034 chars - ✅ Generated successfully
- ID 363: 19,799 chars - ✅ Generated successfully

**Key Difference**: AI and Tech uses single-voice narrative mode with standard TTS API, not Text-to-Dialogue API.

## Recommended Fixes

### Short Term
1. **Skip this episode** - The 26,935 char script may be too large for reliable dialogue generation
2. **Increase API timeout** - Change from 120s to 300s for Text-to-Dialogue API specifically
3. **Add inter-chunk delays** - Insert 2-3 second delay between dialogue chunk API calls

### Long Term
1. **Implement max script length** for dialogue mode (e.g., 20,000 chars)
2. **Add retry logic with exponential backoff** for Text-to-Dialogue timeouts
3. **Monitor ElevenLabs API status** before bulk regenerations
4. **Consider splitting very long scripts** into multiple digest episodes

## Code References

**Timeout Configuration:**
- `src/audio/audio_generator.py:277` - TTS API timeout (120s)
- `src/audio/audio_generator.py:548` - Text-to-Dialogue API timeout (120s)

**Chunking Logic:**
- `src/audio/dialogue_chunker.py:39` - MAX_CHUNK_SIZE = 2800
- `src/audio/audio_generator.py:577-647` - Dialogue chunk generation loop

**Script Content:**
- Database digest ID 364
- First 1000 chars show `SPEAKER_1 [Jamal, excited]:` format
- Contains audio tags like `[excited]`, `[thoughtful]`, `[serious]`

## Next Steps

If this issue persists:
1. Check ElevenLabs API status dashboard
2. Test with shorter Social Movements scripts first
3. Consider contacting ElevenLabs support about Text-to-Dialogue timeout behavior
4. Implement script length warnings in digest generation phase

## Date
2025-11-11

## Related Files
- `regenerate_failed.py` - Script that attempted regeneration
- `src/audio/audio_generator.py` - Audio generation with timeout settings
- `src/audio/dialogue_chunker.py` - Dialogue script chunking logic
