"""
Channel Management CLI System.
Provides command-line interface for managing YouTube channels.
"""

import click
import logging
from datetime import datetime
from typing import List, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm

from ..database.models import Channel, get_channel_repo, get_database_manager
from ..youtube.channel_resolver import resolve_channel, ChannelInfo
from ..youtube.video_discovery import VideoDiscovery, ChannelHealthMonitor, discover_videos_for_channel
from ..utils.logging_config import setup_logging

# Setup rich console for better CLI output
console = Console()
logger = logging.getLogger(__name__)

class ChannelManager:
    """Manages YouTube channel operations via CLI"""
    
    def __init__(self):
        self.db_manager = get_database_manager()
        self.channel_repo = get_channel_repo(self.db_manager)
        self.health_monitor = ChannelHealthMonitor()
    
    def add_channel(self, input_str: str, auto_confirm: bool = False) -> bool:
        """
        Add a new channel to the system.
        
        Args:
            input_str: YouTube URL, handle, or channel name
            auto_confirm: Skip confirmation prompt
            
        Returns:
            True if channel was added successfully
        """
        try:
            console.print(f"[blue]Resolving channel information for: {input_str}[/blue]")
            
            # Resolve channel information
            channel_info = resolve_channel(input_str)
            if not channel_info:
                console.print(f"[red]❌ Could not resolve channel information for: {input_str}[/red]")
                return False
            
            # Check if channel already exists
            existing_channel = self.channel_repo.get_by_id(channel_info.channel_id)
            if existing_channel:
                console.print(f"[yellow]⚠️  Channel already exists: {existing_channel.channel_name}[/yellow]")
                
                if not existing_channel.active:
                    if auto_confirm or Confirm.ask("Channel is inactive. Reactivate it?"):
                        self._reactivate_channel(existing_channel.channel_id)
                        console.print(f"[green]✅ Reactivated channel: {existing_channel.channel_name}[/green]")
                        return True
                return False
            
            # Display channel information
            self._display_channel_info(channel_info)
            
            # Confirm addition
            if not auto_confirm and not Confirm.ask("Add this channel?"):
                console.print("[yellow]Channel addition cancelled[/yellow]")
                return False
            
            # Create channel object
            channel = Channel(
                channel_id=channel_info.channel_id,
                channel_name=channel_info.channel_name,
                channel_url=channel_info.channel_url,
                active=True
            )
            
            # Save to database
            channel_id = self.channel_repo.create(channel)
            console.print(f"[green]✅ Successfully added channel: {channel_info.channel_name} (ID: {channel_id})[/green]")
            
            # Test video discovery
            if auto_confirm or Confirm.ask("Test video discovery for this channel?"):
                self._test_video_discovery(channel)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to add channel {input_str}: {e}")
            console.print(f"[red]❌ Error adding channel: {e}[/red]")
            return False
    
    def remove_channel(self, channel_identifier: str, auto_confirm: bool = False) -> bool:
        """
        Remove a channel from the system.
        
        Args:
            channel_identifier: Channel ID or name
            auto_confirm: Skip confirmation prompt
            
        Returns:
            True if channel was removed successfully
        """
        try:
            # Find channel
            channel = self._find_channel(channel_identifier)
            if not channel:
                console.print(f"[red]❌ Channel not found: {channel_identifier}[/red]")
                return False
            
            # Display channel info
            console.print(f"[yellow]Channel to remove: {channel.channel_name} ({channel.channel_id})[/yellow]")
            console.print(f"Status: {'Active' if channel.active else 'Inactive'}")
            console.print(f"Videos processed: {channel.total_videos_processed}")
            console.print(f"Consecutive failures: {channel.consecutive_failures}")
            
            # Confirm removal
            if not auto_confirm and not Confirm.ask("⚠️  This will permanently delete the channel and all associated episodes. Continue?"):
                console.print("[yellow]Channel removal cancelled[/yellow]")
                return False
            
            # Delete channel
            deleted_count = self.channel_repo.delete(channel.channel_id)
            if deleted_count > 0:
                console.print(f"[green]✅ Successfully removed channel: {channel.channel_name}[/green]")
                return True
            else:
                console.print(f"[red]❌ Failed to remove channel: {channel.channel_name}[/red]")
                return False
                
        except Exception as e:
            logger.error(f"Failed to remove channel {channel_identifier}: {e}")
            console.print(f"[red]❌ Error removing channel: {e}[/red]")
            return False
    
    def list_channels(self, show_inactive: bool = False, show_health: bool = False) -> None:
        """
        List all channels in the system.
        
        Args:
            show_inactive: Include inactive channels
            show_health: Show detailed health information
        """
        try:
            if show_inactive:
                # Get all channels (would need a new method in repository)
                active_channels = self.channel_repo.get_all_active()
                console.print("[yellow]Note: Only showing active channels (inactive filter not yet implemented)[/yellow]")
                channels = active_channels
            else:
                channels = self.channel_repo.get_all_active()
            
            if not channels:
                console.print("[yellow]No channels found[/yellow]")
                return
            
            # Create table
            table = Table(title=f"YouTube Channels ({len(channels)} found)")
            table.add_column("Name", style="cyan", no_wrap=True)
            table.add_column("Channel ID", style="blue")
            table.add_column("Status", style="green")
            
            if show_health:
                table.add_column("Videos", style="yellow")
                table.add_column("Failures", style="red")
                table.add_column("Last Checked", style="magenta")
            
            # Add rows
            for channel in channels:
                status = "✅ Active" if channel.active else "❌ Inactive"
                
                row = [
                    channel.channel_name,
                    channel.channel_id,
                    status
                ]
                
                if show_health:
                    last_checked = channel.last_checked.strftime("%Y-%m-%d %H:%M") if channel.last_checked else "Never"
                    row.extend([
                        str(channel.total_videos_processed),
                        str(channel.consecutive_failures),
                        last_checked
                    ])
                
                table.add_row(*row)
            
            console.print(table)
            
            # Show unhealthy channels if health monitoring is enabled
            if show_health:
                unhealthy = self.health_monitor.get_unhealthy_channels(self.channel_repo)
                if unhealthy:
                    console.print(f"\n[red]⚠️  {len(unhealthy)} channels need attention due to consecutive failures[/red]")
                    for channel in unhealthy:
                        console.print(f"  • {channel.channel_name}: {channel.consecutive_failures} failures")
                        
        except Exception as e:
            logger.error(f"Failed to list channels: {e}")
            console.print(f"[red]❌ Error listing channels: {e}[/red]")
    
    def test_channel(self, channel_identifier: str, days_back: int = 1) -> None:
        """
        Test video discovery for a specific channel.
        
        Args:
            channel_identifier: Channel ID or name
            days_back: Number of days to look back for videos
        """
        try:
            # Find channel
            channel = self._find_channel(channel_identifier)
            if not channel:
                console.print(f"[red]❌ Channel not found: {channel_identifier}[/red]")
                return
            
            console.print(f"[blue]Testing video discovery for: {channel.channel_name}[/blue]")
            console.print(f"Looking for videos from the last {days_back} day(s)...")
            
            # Discover videos
            videos = discover_videos_for_channel(channel, days_back)
            
            if not videos:
                console.print("[yellow]No qualifying videos found[/yellow]")
                return
            
            # Display results
            table = Table(title=f"Discovered Videos ({len(videos)} found)")
            table.add_column("Title", style="cyan", max_width=50)
            table.add_column("Video ID", style="blue")
            table.add_column("Duration", style="green")
            table.add_column("Published", style="magenta")
            
            for video in videos:
                duration_min = video.duration_seconds // 60
                duration_sec = video.duration_seconds % 60
                duration_str = f"{duration_min}:{duration_sec:02d}"
                
                table.add_row(
                    video.title[:47] + "..." if len(video.title) > 50 else video.title,
                    video.video_id,
                    duration_str,
                    video.published_date.strftime("%Y-%m-%d %H:%M")
                )
            
            console.print(table)
            
        except Exception as e:
            logger.error(f"Failed to test channel {channel_identifier}: {e}")
            console.print(f"[red]❌ Error testing channel: {e}[/red]")
    
    def channel_health(self) -> None:
        """Display channel health overview"""
        try:
            all_channels = self.channel_repo.get_all_active()
            unhealthy_channels = self.health_monitor.get_unhealthy_channels(self.channel_repo)
            
            # Overview stats
            console.print("[bold blue]Channel Health Overview[/bold blue]")
            console.print(f"Total active channels: {len(all_channels)}")
            console.print(f"Healthy channels: {len(all_channels) - len(unhealthy_channels)}")
            console.print(f"Unhealthy channels: {len(unhealthy_channels)}")
            
            if unhealthy_channels:
                console.print("\n[red]Channels needing attention:[/red]")
                
                table = Table()
                table.add_column("Channel Name", style="cyan")
                table.add_column("Consecutive Failures", style="red")
                table.add_column("Total Failed", style="yellow")
                table.add_column("Last Checked", style="magenta")
                
                for channel in unhealthy_channels:
                    last_checked = channel.last_checked.strftime("%Y-%m-%d %H:%M") if channel.last_checked else "Never"
                    table.add_row(
                        channel.channel_name,
                        str(channel.consecutive_failures),
                        str(channel.total_videos_failed),
                        last_checked
                    )
                
                console.print(table)
            else:
                console.print("\n[green]✅ All channels are healthy![/green]")
                
        except Exception as e:
            logger.error(f"Failed to check channel health: {e}")
            console.print(f"[red]❌ Error checking channel health: {e}[/red]")
    
    def _find_channel(self, identifier: str) -> Optional[Channel]:
        """Find channel by ID or name"""
        # First try by channel ID
        channel = self.channel_repo.get_by_id(identifier)
        if channel:
            return channel
        
        # Then try by name (get all and search)
        all_channels = self.channel_repo.get_all_active()
        for channel in all_channels:
            if channel.channel_name.lower() == identifier.lower():
                return channel
        
        return None
    
    def _display_channel_info(self, channel_info: ChannelInfo) -> None:
        """Display channel information in a formatted way"""
        console.print("\n[bold green]Channel Information:[/bold green]")
        console.print(f"Name: {channel_info.channel_name}")
        console.print(f"Channel ID: {channel_info.channel_id}")
        console.print(f"URL: {channel_info.channel_url}")
        
        if channel_info.subscriber_count:
            console.print(f"Subscribers: {channel_info.subscriber_count:,}")
        
        if channel_info.upload_count:
            console.print(f"Total Uploads: {channel_info.upload_count:,}")
        
        if channel_info.description:
            desc = channel_info.description[:200] + "..." if len(channel_info.description) > 200 else channel_info.description
            console.print(f"Description: {desc}")
        
        console.print()
    
    def _test_video_discovery(self, channel: Channel) -> None:
        """Test video discovery for a channel"""
        try:
            console.print(f"[blue]Testing video discovery for {channel.channel_name}...[/blue]")
            videos = discover_videos_for_channel(channel, days_back=3)  # Look back 3 days for testing
            
            if videos:
                console.print(f"[green]✅ Found {len(videos)} qualifying videos[/green]")
                for video in videos[:3]:  # Show first 3
                    duration_min = video.duration_seconds // 60
                    console.print(f"  • {video.title} ({duration_min} min)")
            else:
                console.print("[yellow]⚠️  No qualifying videos found in the last 3 days[/yellow]")
                
        except Exception as e:
            console.print(f"[red]❌ Video discovery test failed: {e}[/red]")
    
    def _reactivate_channel(self, channel_id: str) -> None:
        """Reactivate an inactive channel"""
        # This would need a new method in the repository
        # For now, we'll log it
        logger.info(f"Channel reactivation requested for {channel_id}")

# CLI Commands using Click

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
def channels(verbose):
    """Manage YouTube channels for the digest system"""
    if verbose:
        setup_logging(log_level='DEBUG')
    else:
        setup_logging(log_level='INFO')

@channels.command()
@click.argument('channel_input')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts')
def add(channel_input, yes):
    """Add a new YouTube channel"""
    manager = ChannelManager()
    manager.add_channel(channel_input, auto_confirm=yes)

@channels.command()
@click.argument('channel_identifier')
@click.option('--yes', '-y', is_flag=True, help='Skip confirmation prompts')
def remove(channel_identifier, yes):
    """Remove a YouTube channel"""
    manager = ChannelManager()
    manager.remove_channel(channel_identifier, auto_confirm=yes)

@channels.command()
@click.option('--inactive', is_flag=True, help='Include inactive channels')
@click.option('--health', is_flag=True, help='Show health information')
def list(inactive, health):
    """List all channels"""
    manager = ChannelManager()
    manager.list_channels(show_inactive=inactive, show_health=health)

@channels.command()
@click.argument('channel_identifier')
@click.option('--days', '-d', default=1, help='Days to look back for videos')
def test(channel_identifier, days):
    """Test video discovery for a channel"""
    manager = ChannelManager()
    manager.test_channel(channel_identifier, days_back=days)

@channels.command()
def health():
    """Show channel health overview"""
    manager = ChannelManager()
    manager.channel_health()

if __name__ == '__main__':
    channels()