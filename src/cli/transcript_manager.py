"""
CLI for transcript processing operations.
Provides commands for fetching, validating, and managing video transcripts.
"""

import click
import logging
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, TextColumn, BarColumn, TimeElapsedColumn
from pathlib import Path
import json
from typing import Optional

from ..database.models import get_episode_repo, get_database_manager
from ..youtube.transcript_processor import create_transcript_pipeline, TranscriptProcessor
from ..utils.logging_config import setup_logging

# Initialize components
console = Console()
setup_logging()
logger = logging.getLogger(__name__)

@click.group()
@click.pass_context
def transcript(ctx):
    """Transcript processing commands for YouTube videos."""
    ctx.ensure_object(dict)

@transcript.command()
@click.option('--video-id', '-v', help='Process specific video ID')
@click.option('--limit', '-l', type=int, help='Maximum number of videos to process')
@click.option('--force', '-f', is_flag=True, help='Force reprocess existing transcripts')
def fetch(video_id: Optional[str], limit: Optional[int], force: bool):
    """Fetch transcripts for pending episodes."""
    console.print(Panel("🎬 Transcript Fetching", style="bold blue"))
    
    try:
        # Get repositories and pipeline
        episode_repo = get_episode_repo()
        pipeline = create_transcript_pipeline(episode_repo)
        
        if video_id:
            # Process specific video
            episode = episode_repo.get_by_video_id(video_id)
            if not episode:
                console.print(f"❌ Episode not found: {video_id}", style="red")
                return
            
            if episode.transcript_path and not force:
                console.print(f"ℹ️ Episode already has transcript: {video_id}", style="yellow")
                console.print("Use --force to reprocess")
                return
            
            console.print(f"Processing transcript for: {episode.title}")
            success = pipeline.process_episode(episode)
            
            if success:
                console.print("✅ Transcript processed successfully", style="green")
            else:
                console.print("❌ Failed to process transcript", style="red")
        
        else:
            # Process pending episodes
            if force:
                # If force flag, process all episodes regardless of status
                episodes = episode_repo.get_by_status('pending')
                episodes.extend(episode_repo.get_by_status('transcribed'))
                episodes.extend(episode_repo.get_by_status('scored'))
            else:
                episodes = episode_repo.get_by_status('pending')
            
            if limit:
                episodes = episodes[:limit]
            
            if not episodes:
                console.print("ℹ️ No episodes found for transcript processing", style="yellow")
                return
            
            console.print(f"Processing {len(episodes)} episodes...")
            
            # Process with progress bar
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                "[progress.percentage]{task.percentage:>3.0f}%",
                TimeElapsedColumn(),
                console=console
            ) as progress:
                
                task = progress.add_task("Processing transcripts...", total=len(episodes))
                
                stats = {'successful': 0, 'failed': 0}
                
                for episode in episodes:
                    progress.update(task, description=f"Processing: {episode.title[:30]}...")
                    
                    if pipeline.process_episode(episode):
                        stats['successful'] += 1
                    else:
                        stats['failed'] += 1
                    
                    progress.advance(task)
            
            # Show results
            console.print("\n📊 Processing Summary:")
            console.print(f"✅ Successful: {stats['successful']}")
            console.print(f"❌ Failed: {stats['failed']}")
            console.print(f"📝 Total: {len(episodes)}")
    
    except Exception as e:
        logger.error(f"Error during transcript fetching: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.option('--status', '-s', 
              type=click.Choice(['pending', 'transcribed', 'scored', 'failed']),
              default='transcribed',
              help='Episode status to list')
@click.option('--limit', '-l', type=int, default=10, help='Maximum number of episodes to show')
def list(status: str, limit: int):
    """List episodes with transcript information."""
    console.print(Panel(f"📋 Episodes with status: {status}", style="bold blue"))
    
    try:
        episode_repo = get_episode_repo()
        episodes = episode_repo.get_by_status(status)
        
        if limit:
            episodes = episodes[:limit]
        
        if not episodes:
            console.print(f"No episodes found with status: {status}", style="yellow")
            return
        
        # Create table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Video ID", style="cyan")
        table.add_column("Title", style="white", max_width=40)
        table.add_column("Words", justify="right")
        table.add_column("Status", style="green")
        table.add_column("Transcript Path", style="dim")
        
        for episode in episodes:
            word_count = str(episode.transcript_word_count) if episode.transcript_word_count else "-"
            transcript_file = Path(episode.transcript_path).name if episode.transcript_path else "-"
            
            table.add_row(
                episode.video_id,
                episode.title[:37] + "..." if len(episode.title) > 40 else episode.title,
                word_count,
                episode.status,
                transcript_file
            )
        
        console.print(table)
        console.print(f"\nShowing {len(episodes)} episodes")
    
    except Exception as e:
        logger.error(f"Error listing episodes: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.argument('video_id')
def show(video_id: str):
    """Show transcript details for a specific video."""
    console.print(Panel(f"📄 Transcript Details: {video_id}", style="bold blue"))
    
    try:
        episode_repo = get_episode_repo()
        episode = episode_repo.get_by_video_id(video_id)
        
        if not episode:
            console.print(f"❌ Episode not found: {video_id}", style="red")
            return
        
        # Show episode details
        console.print(f"🎬 Title: {episode.title}")
        console.print(f"📅 Published: {episode.published_date.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"⏱️ Duration: {episode.duration_seconds}s")
        console.print(f"📊 Status: {episode.status}")
        
        if episode.transcript_path:
            console.print(f"📁 Transcript File: {episode.transcript_path}")
            console.print(f"📝 Word Count: {episode.transcript_word_count}")
            console.print(f"🕒 Fetched: {episode.transcript_fetched_at}")
            
            # Load and show transcript preview
            processor = TranscriptProcessor()
            transcript_data = processor.load_transcript(episode.transcript_path)
            
            if transcript_data:
                console.print(f"\n🌍 Language: {transcript_data.language}")
                console.print(f"🤖 Auto-generated: {transcript_data.is_auto_generated}")
                console.print(f"⏲️ Total Duration: {transcript_data.total_duration:.1f}s")
                console.print(f"📊 Segments: {len(transcript_data.segments)}")
                
                # Show validation results
                is_valid, reason = processor.validate_transcript_quality(transcript_data)
                quality_style = "green" if is_valid else "red"
                console.print(f"✅ Quality: {reason}", style=quality_style)
                
                # Show first few segments
                console.print("\n📝 Transcript Preview:")
                text_preview = processor.get_transcript_text(transcript_data)[:300]
                console.print(f"{text_preview}..." if len(text_preview) >= 300 else text_preview)
            else:
                console.print("❌ Failed to load transcript file", style="red")
        else:
            console.print("❌ No transcript available", style="yellow")
            if episode.failure_reason:
                console.print(f"💥 Failure Reason: {episode.failure_reason}")
    
    except Exception as e:
        logger.error(f"Error showing transcript: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.option('--status', '-s', 
              type=click.Choice(['all', 'pending', 'transcribed', 'scored', 'failed']),
              default='all',
              help='Status filter for statistics')
def stats(status: str):
    """Show transcript processing statistics."""
    console.print(Panel("📊 Transcript Statistics", style="bold blue"))
    
    try:
        episode_repo = get_episode_repo()
        
        # Get episode counts by status
        if status == 'all':
            all_episodes = []
            for s in ['pending', 'transcribed', 'scored', 'failed']:
                all_episodes.extend(episode_repo.get_by_status(s))
            episodes = all_episodes
        else:
            episodes = episode_repo.get_by_status(status)
        
        if not episodes:
            console.print(f"No episodes found with status: {status}", style="yellow")
            return
        
        # Calculate statistics
        total_episodes = len(episodes)
        transcribed_episodes = [e for e in episodes if e.transcript_path]
        total_words = sum(e.transcript_word_count or 0 for e in transcribed_episodes)
        avg_words = total_words / len(transcribed_episodes) if transcribed_episodes else 0
        
        # Status breakdown
        status_counts = {}
        for episode in episodes:
            status_counts[episode.status] = status_counts.get(episode.status, 0) + 1
        
        # Create statistics table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="white")
        
        table.add_row("Total Episodes", str(total_episodes))
        table.add_row("With Transcripts", str(len(transcribed_episodes)))
        table.add_row("Total Words", f"{total_words:,}")
        table.add_row("Average Words/Episode", f"{avg_words:.0f}")
        
        console.print(table)
        
        # Status breakdown
        if len(status_counts) > 1:
            console.print("\n📈 Status Breakdown:")
            status_table = Table(show_header=True, header_style="bold magenta")
            status_table.add_column("Status", style="cyan")
            status_table.add_column("Count", justify="right", style="white")
            status_table.add_column("Percentage", justify="right", style="green")
            
            for s, count in status_counts.items():
                percentage = (count / total_episodes) * 100
                status_table.add_row(s, str(count), f"{percentage:.1f}%")
            
            console.print(status_table)
    
    except Exception as e:
        logger.error(f"Error generating statistics: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.argument('video_id')
@click.option('--output', '-o', help='Output file path (default: stdout)')
def export(video_id: str, output: Optional[str]):
    """Export transcript data for a video."""
    console.print(Panel(f"📤 Exporting Transcript: {video_id}", style="bold blue"))
    
    try:
        episode_repo = get_episode_repo()
        episode = episode_repo.get_by_video_id(video_id)
        
        if not episode:
            console.print(f"❌ Episode not found: {video_id}", style="red")
            return
        
        if not episode.transcript_path:
            console.print(f"❌ No transcript available for: {video_id}", style="red")
            return
        
        # Load transcript data
        processor = TranscriptProcessor()
        transcript_data = processor.load_transcript(episode.transcript_path)
        
        if not transcript_data:
            console.print(f"❌ Failed to load transcript: {episode.transcript_path}", style="red")
            return
        
        # Export options
        export_data = {
            'video_id': video_id,
            'title': episode.title,
            'published_date': episode.published_date.isoformat(),
            'duration_seconds': episode.duration_seconds,
            'transcript': {
                'language': transcript_data.language,
                'is_auto_generated': transcript_data.is_auto_generated,
                'word_count': transcript_data.word_count,
                'total_duration': transcript_data.total_duration,
                'full_text': processor.get_transcript_text(transcript_data),
                'segments': [
                    {
                        'start': seg.start,
                        'duration': seg.duration,
                        'text': seg.text
                    }
                    for seg in transcript_data.segments
                ]
            }
        }
        
        # Output to file or stdout
        if output:
            with open(output, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            console.print(f"✅ Transcript exported to: {output}", style="green")
        else:
            console.print(json.dumps(export_data, indent=2, ensure_ascii=False))
    
    except Exception as e:
        logger.error(f"Error exporting transcript: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.option('--video-id', '-v', default='dQw4w9WgXcQ', help='Video ID to test connectivity with')
def test_connectivity(video_id: str):
    """Test YouTube transcript API connectivity and IP blocking status."""
    console.print(Panel("🔗 Testing YouTube Transcript API Connectivity", style="bold blue"))
    
    try:
        processor = TranscriptProcessor()
        results = processor.test_connectivity(video_id)
        
        # Display results
        console.print(f"🎯 Testing with video: {video_id}")
        console.print()
        
        if results['can_list_transcripts']:
            console.print("✅ Can list transcripts", style="green")
            console.print(f"📊 Found {results['available_transcripts']} transcript options")
        else:
            console.print("❌ Cannot list transcripts", style="red")
        
        if results['can_fetch_transcript']:
            console.print("✅ Can fetch transcript content", style="green")
            console.print("🎉 YouTube transcript API is working normally")
        else:
            console.print("❌ Cannot fetch transcript content", style="red")
        
        if results['ip_blocked']:
            console.print("🚫 IP appears to be blocked by YouTube", style="red")
            console.print("💡 Possible solutions:")
            console.print("  • Wait 24-48 hours for IP block to expire")
            console.print("  • Use residential proxy service (e.g., Webshare)")
            console.print("  • Implement longer delays between requests")
        
        if results['error_message']:
            console.print(f"\n💥 Error details: {results['error_message']}", style="dim")
    
    except Exception as e:
        logger.error(f"Error testing connectivity: {e}")
        console.print(f"❌ Error: {e}", style="red")

@transcript.command()
@click.option('--dry-run', is_flag=True, help='Show what would be validated without making changes')
def validate(dry_run: bool):
    """Validate all transcript files and mark quality issues."""
    console.print(Panel("🔍 Transcript Validation", style="bold blue"))
    
    try:
        episode_repo = get_episode_repo()
        processor = TranscriptProcessor()
        
        # Get all transcribed episodes
        episodes = episode_repo.get_by_status('transcribed')
        episodes.extend(episode_repo.get_by_status('scored'))
        
        if not episodes:
            console.print("No transcribed episodes found for validation", style="yellow")
            return
        
        console.print(f"Validating {len(episodes)} transcripts...")
        
        valid_count = 0
        invalid_count = 0
        error_count = 0
        
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Validating transcripts...", total=len(episodes))
            
            for episode in episodes:
                if not episode.transcript_path:
                    error_count += 1
                    progress.advance(task)
                    continue
                
                try:
                    transcript_data = processor.load_transcript(episode.transcript_path)
                    if not transcript_data:
                        error_count += 1
                        progress.advance(task)
                        continue
                    
                    is_valid, reason = processor.validate_transcript_quality(transcript_data)
                    
                    if is_valid:
                        valid_count += 1
                    else:
                        invalid_count += 1
                        
                        if not dry_run:
                            # Mark episode with quality issue
                            episode_repo.mark_failure(episode.video_id, f"Quality validation failed: {reason}")
                
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error validating {episode.video_id}: {e}")
                
                progress.advance(task)
        
        # Show results
        console.print("\n📊 Validation Summary:")
        console.print(f"✅ Valid: {valid_count}")
        console.print(f"❌ Invalid: {invalid_count}")
        console.print(f"💥 Errors: {error_count}")
        console.print(f"📝 Total: {len(episodes)}")
        
        if dry_run:
            console.print("\n💡 This was a dry run - no changes made")
        elif invalid_count > 0:
            console.print(f"\n⚠️ {invalid_count} episodes marked with quality issues")
    
    except Exception as e:
        logger.error(f"Error during validation: {e}")
        console.print(f"❌ Error: {e}", style="red")

if __name__ == '__main__':
    transcript()