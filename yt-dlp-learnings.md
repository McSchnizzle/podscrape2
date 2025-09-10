# yt-dlp Integration Research & Implementation Plan

## Overview

Research findings and implementation plan for integrating yt-dlp to support YouTube RSS feeds in the podcast transcription pipeline.

## Research Summary

### Technical Feasibility ✅

**Tool Information:**
- **License**: Unlicense (public domain) - completely free
- **Version**: 2025.9.5 (already installed)
- **Dependencies**: Python 3.7+, FFmpeg (✅ available)
- **Maintenance**: Actively maintained with regular updates

**Audio Extraction Capabilities:**
- Supports 1000+ sites including YouTube
- Audio-only extraction with multiple format options (MP3, WAV, AAC, etc.)
- Quality options: 58kbps to 320kbps+ 
- Uses FFmpeg for conversion (already available)
- Tested successfully with Wes Roth video (527 seconds, 48 audio formats available)

**Rate Limiting & Performance:**
- Built-in rate limiting with `--rate-limit` flag
- No hard API limits (doesn't use YouTube API directly)
- Robust retry mechanisms for network issues
- Performance comparable to traditional podcast downloads

### Legal & Compliance Considerations ⚠️

**YouTube Terms of Service:**
- Downloading YouTube content technically violates ToS
- However, enforcement is rare for individual/research use
- YouTube historically shows "no desire to penalize users"

**Copyright Considerations:**
- Tool itself is legal, content may be copyrighted
- Need permission from content creators for commercial use
- Risk varies by jurisdiction and use case

**Risk Assessment:**
- **Personal/Research use**: Generally low risk
- **Commercial podcast business**: Higher legal risk
- **Recommendation**: Consider reaching out to creators for permission

### Current Feed Status

**In Database (22 total):**
- **14 Traditional Podcast Feeds**: Work with current AudioProcessor
- **8 YouTube Feeds**: Require yt-dlp integration

**YouTube Feeds Identified:**
- Wes Roth (UCqcbQf6yw5KzRoDDcZ_wBSw)
- Matt Wolfe (UChpleBmo18P08aKCIgti38g)
- How I AI (UCRYY7IEbkHLH_ScJCu9eWDQ)
- The AI Advantage (UCHhYXsLBEVVnbvsq57n1MTQ)
- AI Daily Brief (UCKelCK4ZaO6HeEI1KQjqzWA)
- All About AI (UCR9j1jqqB5Rse69wjUnbYwA)
- Indy Dev Dan (UC_x36zCEGilGpB1m-V4gmjg)
- Robin (UCy71Sv5TVBbn5BYETRQV22Q)

## Implementation Plan

### Phase 1: Detection System

**Goal**: Automatically detect YouTube URLs and route them appropriately

**Implementation:**
```python
import re
from urllib.parse import urlparse

class URLClassifier:
    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """Detect if URL is from YouTube"""
        youtube_patterns = [
            r'youtube\.com/watch',
            r'youtu\.be/',
            r'youtube\.com/shorts',
            r'youtube\.com/embed'
        ]
        return any(re.search(pattern, url) for pattern in youtube_patterns)
    
    @staticmethod
    def is_direct_audio_url(url: str) -> bool:
        """Detect if URL is direct audio download"""
        audio_extensions = ['.mp3', '.wav', '.m4a', '.aac', '.ogg']
        return any(url.lower().endswith(ext) for ext in audio_extensions)
```

### Phase 2: YouTube Audio Processor

**Goal**: Create specialized processor for YouTube content

**Implementation:**
```python
import yt_dlp
from pathlib import Path
import tempfile

class YouTubeAudioProcessor:
    def __init__(self, output_dir: str = "audio_cache"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def download_youtube_audio(self, youtube_url: str, episode_guid: str) -> str:
        """
        Download audio from YouTube video
        
        Args:
            youtube_url: YouTube video URL
            episode_guid: Unique identifier for episode
            
        Returns:
            Path to downloaded audio file
        """
        # Configure yt-dlp options
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': str(self.output_dir / f'{episode_guid}.%(ext)s'),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',  # Good quality for transcription
            }],
            'quiet': True,
            'no_warnings': True,
            # Rate limiting to be respectful
            'ratelimit': 50 * 1024,  # 50KB/s limit
            'retries': 3,
            'fragment_retries': 3,
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to get metadata
                info = ydl.extract_info(youtube_url, download=False)
                
                # Validate duration (skip very long videos)
                duration = info.get('duration', 0)
                if duration > 7200:  # 2 hours max
                    raise ValueError(f"Video too long: {duration}s")
                
                # Download audio
                ydl.download([youtube_url])
                
                # Find the downloaded file
                audio_file = self.output_dir / f'{episode_guid}.mp3'
                if audio_file.exists():
                    return str(audio_file)
                else:
                    raise FileNotFoundError("Downloaded audio file not found")
                    
        except Exception as e:
            logger.error(f"YouTube download failed for {youtube_url}: {e}")
            raise
    
    def get_youtube_metadata(self, youtube_url: str) -> dict:
        """Extract metadata without downloading"""
        ydl_opts = {'quiet': True, 'no_warnings': True}
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            
            return {
                'title': info.get('title'),
                'duration': info.get('duration'),
                'uploader': info.get('uploader'),
                'upload_date': info.get('upload_date'),
                'view_count': info.get('view_count'),
                'description': info.get('description', '')[:500]  # Truncate
            }
```

### Phase 3: Enhanced AudioProcessor Integration

**Goal**: Extend existing AudioProcessor to handle both traditional and YouTube feeds

**Implementation:**
```python
class EnhancedAudioProcessor(AudioProcessor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.youtube_processor = YouTubeAudioProcessor(
            output_dir=self.audio_cache_dir
        )
        self.url_classifier = URLClassifier()
    
    def download_audio(self, audio_url: str, episode_guid: str, **kwargs) -> str:
        """
        Enhanced download that handles both traditional and YouTube URLs
        """
        if self.url_classifier.is_youtube_url(audio_url):
            logger.info(f"Detected YouTube URL, using yt-dlp: {audio_url}")
            return self.youtube_processor.download_youtube_audio(
                audio_url, episode_guid
            )
        else:
            # Use existing traditional download method
            return super().download_audio(audio_url, episode_guid, **kwargs)
    
    def get_audio_metadata(self, audio_url: str) -> dict:
        """Get metadata for any audio source"""
        if self.url_classifier.is_youtube_url(audio_url):
            return self.youtube_processor.get_youtube_metadata(audio_url)
        else:
            # Traditional podcast metadata extraction
            return self._get_traditional_metadata(audio_url)
```

### Phase 4: RSS Feed Handling Updates

**Goal**: Update feed parser to extract YouTube video URLs from RSS

**Current Issue**: YouTube RSS feeds provide video page URLs, not direct audio URLs

**Solution:**
```python
class EnhancedFeedParser(FeedParser):
    def extract_audio_url(self, entry) -> str:
        """
        Extract audio URL from RSS entry, handling both traditional and YouTube feeds
        """
        # Traditional podcast feeds
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enclosure in entry.enclosures:
                if self._is_audio_enclosure(enclosure):
                    return enclosure.href
        
        # YouTube feeds - use the video page URL
        if hasattr(entry, 'link'):
            link = entry.link
            if URLClassifier.is_youtube_url(link):
                return link  # yt-dlp will handle this
        
        # Fallback
        raise ValueError("No valid audio URL found in RSS entry")
```

### Phase 5: Configuration & Feature Flags

**Goal**: Make YouTube support optional and configurable

**Implementation:**
```python
# config/youtube_config.json
{
    "youtube_enabled": false,
    "youtube_settings": {
        "max_duration_seconds": 7200,
        "audio_quality": "128",
        "rate_limit_kbps": 50,
        "max_retries": 3,
        "timeout_seconds": 300
    },
    "legal_disclaimer": "YouTube content download may violate ToS. Use responsibly."
}

class YouTubeConfig:
    def __init__(self, config_path: str = "config/youtube_config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
    
    @property
    def enabled(self) -> bool:
        return self.config.get('youtube_enabled', False)
    
    def get_ydl_opts(self, episode_guid: str, output_dir: str) -> dict:
        """Generate yt-dlp options from config"""
        settings = self.config['youtube_settings']
        return {
            'format': 'bestaudio',
            'outtmpl': f'{output_dir}/{episode_guid}.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': settings['audio_quality'],
            }],
            'ratelimit': settings['rate_limit_kbps'] * 1024,
            'retries': settings['max_retries'],
            'socket_timeout': settings['timeout_seconds'],
            'quiet': True,
            'no_warnings': True,
        }
```

## Error Handling & Edge Cases

### Common Issues & Solutions

**1. Age-Restricted Videos**
```python
# Add to ydl_opts
'skip_unavailable_fragments': True,
'ignore_errors': True,
```

**2. Geo-Blocked Content**
```python
# Log and skip gracefully
try:
    ydl.download([youtube_url])
except yt_dlp.DownloadError as e:
    if "not available" in str(e).lower():
        logger.warning(f"Video not available in region: {youtube_url}")
        return None
```

**3. Very Long Videos**
```python
# Check duration before download
info = ydl.extract_info(youtube_url, download=False)
duration = info.get('duration', 0)
if duration > MAX_DURATION:
    raise ValueError(f"Video too long: {duration}s > {MAX_DURATION}s")
```

**4. Network Issues**
```python
# Implement exponential backoff
@retry_with_backoff(max_retries=3, backoff_factor=2.0)
def download_with_retry(self, youtube_url: str, episode_guid: str) -> str:
    return self.youtube_processor.download_youtube_audio(youtube_url, episode_guid)
```

## Testing Strategy

### Unit Tests
```python
def test_youtube_url_detection():
    assert URLClassifier.is_youtube_url("https://www.youtube.com/watch?v=ABC123")
    assert URLClassifier.is_youtube_url("https://youtu.be/ABC123")
    assert not URLClassifier.is_youtube_url("https://example.com/podcast.mp3")

def test_youtube_metadata_extraction():
    processor = YouTubeAudioProcessor()
    metadata = processor.get_youtube_metadata(TEST_YOUTUBE_URL)
    assert 'title' in metadata
    assert 'duration' in metadata
```

### Integration Tests
```python
def test_full_youtube_pipeline():
    # Test with actual YouTube video (use short test video)
    processor = EnhancedAudioProcessor()
    audio_path = processor.download_audio(TEST_YOUTUBE_URL, "test-guid")
    assert Path(audio_path).exists()
    assert Path(audio_path).suffix == '.mp3'
```

## Performance Considerations

### Optimization Strategies

**1. Parallel Processing**
- Download multiple YouTube videos concurrently
- Respect rate limits and be good citizens

**2. Caching**
- Cache audio files by video ID to avoid re-downloads
- Cache metadata to reduce API calls

**3. Quality vs Speed**
- Default to 128kbps for transcription (good quality, faster download)
- Allow configuration for higher quality if needed

**4. Monitoring**
- Track download success/failure rates
- Monitor download speeds and durations
- Alert on repeated failures

## Database Schema Updates

### New Fields for YouTube Support

```sql
-- Add YouTube-specific fields to episodes table
ALTER TABLE episodes ADD COLUMN is_youtube_content BOOLEAN DEFAULT FALSE;
ALTER TABLE episodes ADD COLUMN youtube_video_id TEXT;
ALTER TABLE episodes ADD COLUMN youtube_uploader TEXT;
ALTER TABLE episodes ADD COLUMN youtube_view_count INTEGER;

-- Index for YouTube queries
CREATE INDEX idx_episodes_youtube ON episodes(is_youtube_content, youtube_video_id);
```

## Deployment Checklist

### Pre-deployment
- [ ] Legal review of YouTube content usage
- [ ] Test with small subset of YouTube feeds
- [ ] Validate audio quality for transcription
- [ ] Confirm FFmpeg availability in production
- [ ] Set up monitoring and alerting

### Configuration
- [ ] Set appropriate rate limits
- [ ] Configure error handling and retries
- [ ] Set up logging for YouTube operations
- [ ] Enable/disable YouTube support via feature flag

### Monitoring
- [ ] Track YouTube download success rates
- [ ] Monitor download durations
- [ ] Alert on repeated failures or rate limiting
- [ ] Track storage usage for YouTube audio files

## Future Enhancements

### Advanced Features
1. **Quality Selection**: Choose audio quality based on content type
2. **Transcript Integration**: Use YouTube's auto-generated subtitles when available
3. **Batch Processing**: Optimize for processing multiple YouTube videos
4. **Content Filtering**: Skip certain types of content (shorts, livestreams)
5. **Analytics**: Track most successful YouTube channels/content types

### Alternative Approaches
1. **YouTube Transcript API**: Use existing transcripts instead of downloading audio
2. **Webhook Integration**: Real-time processing of new YouTube uploads
3. **ML Content Classification**: Automatically categorize YouTube content

## Conclusion

yt-dlp integration is technically straightforward and would significantly expand the podcast pipeline's capabilities. The main considerations are:

1. **Legal compliance** - Need clear usage guidelines
2. **Performance** - Additional download time and storage
3. **Reliability** - YouTube changes may require yt-dlp updates
4. **Configuration** - Make it optional and configurable

The implementation can be done incrementally, starting with basic download support and expanding to more advanced features over time.