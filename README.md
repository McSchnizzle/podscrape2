# YouTube Transcript Digest System

An automated daily podcast digest system that intelligently curates YouTube content, scores it for topic relevancy, and generates high-quality AI-powered audio summaries.

## 🎯 Overview

This system automatically:
- Collects transcripts from specified YouTube creators
- Scores content against multiple topics using GPT-5-mini  
- Generates topic-based scripts using GPT-5
- Converts scripts to audio using ElevenLabs TTS
- Publishes via RSS feed at podcast.paulrbrown.org

## 🏗️ Architecture

```
YouTube Videos → Transcript Extraction → AI Scoring → Script Generation → TTS → RSS Feed
```

### Core Components
- **Database**: SQLite for episodes, channels, and digests
- **AI Scoring**: GPT-5-mini for relevancy scoring (0.0-1.0)
- **Script Generation**: GPT-5 for topic-based content synthesis  
- **Audio Production**: ElevenLabs TTS with configurable voices
- **Publishing**: GitHub + Vercel for RSS delivery

## 📁 Project Structure

```
podscrape2/
├── src/                    # Source code
│   ├── database/          # Database models and migrations
│   ├── channels/          # YouTube channel management
│   ├── transcripts/       # Transcript fetching and processing
│   ├── scoring/           # AI-powered content scoring
│   ├── generation/        # Script generation
│   ├── audio/             # TTS and audio processing
│   └── publishing/        # GitHub and RSS publishing
├── data/
│   ├── database/          # SQLite database files
│   ├── transcripts/       # Raw transcript files
│   ├── scripts/           # Generated digest scripts
│   ├── completed-tts/     # Generated MP3 files
│   └── logs/              # Execution logs
├── config/
│   ├── channels.json      # YouTube channel configuration
│   └── topics.json        # Topic and voice settings
├── digest_instructions/   # Topic-specific generation instructions
├── music_cache/          # Audio assets for music beds
├── tests/                # Phase-specific test suites
├── docs/
│   ├── podscrape2-prd.md # Product Requirements Document
│   └── tasklist.md       # Development progress tracker
└── daily_digest.py      # Main orchestrator
```

## 🚀 Quick Start

### Prerequisites
- Python 3.9+
- YouTube channels to monitor
- API keys: OpenAI, ElevenLabs, GitHub

### Installation

1. **Clone Repository**
   ```bash
   git clone https://github.com/McSchnizzle/podscrape2.git
   cd podscrape2
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

4. **Initialize Database**
   ```bash
   python src/database/init_db.py
   ```

5. **Add YouTube Channels**
   ```bash
   python src/channels/manage.py add "https://youtube.com/@channelname"
   ```

6. **Run Manual Test**
   ```bash
   python daily_digest.py --manual --date 2025-09-09
   ```

### Configuration

#### API Keys (.env)
```bash
OPENAI_API_KEY=your-openai-api-key-here          # GPT-5 models
ELEVENLABS_API_KEY=your-elevenlabs-key-here      # TTS generation
GITHUB_TOKEN=your-github-token-here              # Repository access
GITHUB_REPOSITORY=your-username/your-repo-name
```

#### Channel Management
```bash
# Add channel
python src/channels/manage.py add "Channel Name or URL"

# List channels  
python src/channels/manage.py list

# Remove channel
python src/channels/manage.py remove "Channel Name"

# Channel health check
python src/channels/manage.py health
```

#### Topic Configuration (config/topics.json)
```json
{
  "topics": [
    {
      "name": "AI News",
      "instruction_file": "AI News.md",
      "voice_id": "elevenlabs_voice_id_1",
      "active": true
    },
    {
      "name": "Tech News and Tech Culture", 
      "instruction_file": "Tech News and Tech Culture.md",
      "voice_id": "elevenlabs_voice_id_2",
      "active": true
    }
  ]
}
```

## 🔄 Daily Operation

### Automated Execution
```bash
# Add to crontab for daily 6 AM execution
0 6 * * * cd /path/to/podscrape2 && python daily_digest.py
```

### Manual Execution
```bash
# Process today's content
python daily_digest.py --manual

# Process specific date
python daily_digest.py --manual --date 2025-09-09

# Debug mode with verbose logging
python daily_digest.py --manual --date 2025-09-09 --debug
```

### Monitoring
```bash
# View recent logs
tail -f data/logs/digest_$(date +%Y%m%d).log

# Check channel health
python src/channels/manage.py health

# Database status
python src/database/status.py
```

## 🧪 Testing

Each development phase includes comprehensive testing:

```bash
# Run phase-specific tests
python tests/test_phase1.py  # Database and configuration
python tests/test_phase2.py  # Channel management
python tests/test_phase3.py  # Transcript processing
# ... etc

# Run integration tests
python tests/test_integration.py

# Run performance tests
python tests/test_performance.py
```

## 📊 Content Flow

### Daily Pipeline
1. **Discovery**: Find new videos from monitored channels
2. **Filtering**: Exclude videos <3 minutes (shorts)
3. **Transcription**: Extract transcripts using youtube-transcript-api
4. **Scoring**: Score each episode against all topics (GPT-5-mini)
5. **Selection**: Include episodes scoring ≥0.65 for each topic
6. **Generation**: Create topic-based scripts (GPT-5)
7. **Audio**: Convert scripts to MP3 (ElevenLabs)
8. **Publishing**: Upload to GitHub and update RSS feed

### Content Scoring
- Each episode scored against all topics (0.0-1.0 scale)
- Threshold: ≥0.65 for inclusion in topic digest
- High-scoring episodes can appear in multiple topic digests
- Empty topics generate "no new episodes today" audio

### Quality Controls
- Minimum 3-minute video duration
- 3-retry limit for transcript failures
- Channel health monitoring (flag after 3 consecutive failure days)
- 25,000 word limit per script
- Audio quality optimized for mobile/Bluetooth playback

## 📱 RSS Feed

**Feed URL**: https://podcast.paulrbrown.org/daily-digest.xml

Note: As of Sep 2025, the project standardized on `daily-digest.xml` (retiring `daily-digest2.xml`). A redirect from `/daily-digest2.xml` to `/daily-digest.xml` is configured in `vercel.json` for backward compatibility.

### Features
- Full RSS 2.0 compliance with podcast extensions
- Daily episodes organized by topic
- Rich metadata: titles, summaries, categories
- Compatible with all major podcast clients
- Automated 14-day retention management

### Episode Naming
- **MP3**: `{topic}_{YYYYMMDD}_{HHMMSS}.mp3`
- **Title**: "{Topic} Daily Digest - {Month DD, YYYY}"
- **No Content**: "No New Episodes Today - {Month DD, YYYY}"

## 🔧 Maintenance

### File Retention
- **Local MP3s**: 7 days automatic cleanup
- **GitHub Assets**: 14 days automatic cleanup
- **Database**: Configurable retention (default: 14 days)
- **Logs**: 30 days automatic cleanup

### Health Monitoring
- Channel failure tracking
- API rate limit monitoring
- Database performance metrics
- Audio generation success rates

### Troubleshooting
```bash
# Check system status
python src/utils/health_check.py

# Repair database
python src/database/repair.py

# Retry failed episodes
python src/utils/retry_failed.py

# Clear cache
python src/utils/clear_cache.py
```

## 🛠️ Development

### Phase-Based Development
See `docs/tasklist.md` for detailed development progress and phase breakdown.

**Current Status**: Phase 0 - Project Setup  
**Next Phase**: Phase 1 - Foundation & Data Layer

### Contributing
1. Follow phase-based development approach
2. Run phase tests before proceeding  
3. Update `tasklist.md` with progress
4. Maintain comprehensive test coverage

### Code Style
- Black formatting
- Type hints required
- Comprehensive error handling
- Detailed logging for debugging

## 📚 Documentation

- **[Product Requirements](docs/podscrape2-prd.md)**: Complete project specification
- **[Task List](docs/tasklist.md)**: Development progress and testing
- **[Topic Instructions](digest_instructions/)**: AI generation guidelines
- **[API Integration Guide](docs/gpt5-implementation-learnings.md)**: GPT-5 implementation details

## 🚨 Important Notes

### Rate Limits & Politeness
- YouTube API: Respectful request spacing
- OpenAI API: Built-in rate limiting
- ElevenLabs: Voice generation quotas
- GitHub API: Release management limits

### Privacy & Compliance
- Transcript-only processing (no audio redistribution)
- Local database storage for privacy
- Fair use compliance for content curation
- No PII storage or processing

### Future Enhancements
- Music bed integration with existing assets
- Advanced audio production features  
- Multi-voice support for different content types
- Enhanced content filtering and relevance detection

---

## 📞 Support

For questions or issues:
1. Check existing logs in `data/logs/`
2. Run health check: `python src/utils/health_check.py`
3. Review phase testing in `docs/tasklist.md`
4. Check API key configuration in `.env`

**Project Status**: 🔄 Active Development  
**Current Phase**: Phase 0 - Project Setup  
**Target Completion**: September 24, 2025
