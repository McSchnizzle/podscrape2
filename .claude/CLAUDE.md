# Project-Specific Guidelines for YouTube Transcript Digest System

## Testing Philosophy

### Real Data Only
**CRITICAL**: Always use real YouTube channels and data for testing. Avoid mock data, mock feeds, or fake channel IDs.

**Reasoning**: 
- Mock data doesn't reveal real-world API behavior and edge cases
- Real channels like @mreflow (Matt Wolfe) and @aiadvantage (The AI Advantage) provide consistent, reliable test data
- Network calls may seem slower but reveal actual integration issues

**Best Practices**:
- Use our established test channels: @mreflow and @aiadvantage
- Test with realistic timeframes (7-day lookback vs 1-day)
- Handle network timeouts gracefully but don't avoid them with mocks
- When testing fails, investigate the root cause rather than mocking around it

### Error Handling
- Network errors and timeouts should be handled gracefully in production code
- Tests should validate error handling behavior, not avoid triggering it
- Log warnings for invalid data but don't fail tests unnecessarily

## Channel Management
- Always use the real channel IDs discovered during Phase 2:
  - Matt Wolfe: UChpleBmo18P08aKCIgti38g
  - The AI Advantage: UCHhYXsLBEVVnbvsq57n1MTQ
- Test video discovery with realistic timeframes (7+ days)
- Validate both success and failure scenarios

## Implementation Notes

### Phase 2 Lessons Learned
- yt-dlp requires proper timeout configuration to prevent hangs
- Video discovery needs realistic lookback periods to find content
- Channel health monitoring works well with real failure scenarios
- CLI interface benefits from testing with actual channels

### Future Phases
- Use the established channels for transcript testing
- Test with real videos that have actual transcripts
- Validate against real API rate limits and behavior
- Build resilience based on actual failure patterns observed