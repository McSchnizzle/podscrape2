# Project-Specific Guidelines for RSS Podcast Transcript Digest System

## Testing Philosophy

### Real Data Only
**CRITICAL**: Always use real RSS podcast feeds and data for testing. Avoid mock data, mock feeds, or fake URLs.

**Reasoning**: 
- Mock data doesn't reveal real-world RSS behavior and edge cases
- Real RSS feeds provide consistent, reliable test data with actual audio content
- Network calls may seem slower but reveal actual integration issues

**Real RSS Feeds for Testing**:
- The Bridge with Peter Mansbridge: https://feeds.simplecast.com/imTmqqal
- Anchor feed: https://anchor.fm/s/e8e55a68/podcast/rss
- The Great Simplification: https://thegreatsimplification.libsyn.com/rss
- Movement Memos: https://feeds.megaphone.fm/movementmemos
- Kultural: https://feed.podbean.com/kultural/feed.xml

**Best Practices**:
- Use the established real RSS feeds above for testing
- Test with realistic timeframes (7-day lookback vs 1-day)
- Handle network timeouts gracefully but don't avoid them with mocks
- When testing fails, investigate the root cause rather than mocking around it

### Error Handling
- Network errors and timeouts should be handled gracefully in production code
- Tests should validate error handling behavior, not avoid triggering it
- Log warnings for invalid data but don't fail tests unnecessarily

## Python Environment
**CRITICAL**: Always use `python3` command, never just `python`
- All CLI commands: `python3 script.py`
- All test execution: `python3 test_script.py`
- All pip installations: `pip3 install package`

## RSS Feed Management
- Always use the real RSS feeds listed above for testing
- Test episode discovery with realistic timeframes (7+ days)
- Validate both success and failure scenarios
- Test audio download with actual podcast CDN URLs

## Implementation Notes

### RSS + Parakeet Architecture
- RSS feed parsing using feedparser for reliable episode discovery
- Audio download and 10-minute chunking for optimal ASR performance
- Nvidia Parakeet ASR for high-quality transcription
- Chunk concatenation maintains speaker context and timing

### Audio Processing Requirements
- FFmpeg required for audio chunking and format conversion
- Audio converted to 16kHz mono for ASR compatibility
- Chunk files cleaned up after transcription to save space
- Support for various podcast audio formats (MP3, AAC, etc.)

### Parakeet ASR Integration
- Use Nvidia's Parakeet RNNT 0.6B model via Hugging Face
- Process audio in 10-minute chunks for memory efficiency
- Concatenate transcripts while preserving timing information
- Graceful fallback if GPU not available (CPU processing)