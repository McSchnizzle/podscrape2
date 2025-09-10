#!/usr/bin/env python3
"""
RSS Feed Generator for RSS Podcast Digest System
Generates RSS 2.0 compliant XML with iTunes podcast extensions
"""

import os
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from pathlib import Path
from dataclasses import dataclass
import logging

from ..utils.logging_config import get_logger
from ..utils.error_handling import PodcastError

logger = get_logger(__name__)

@dataclass
class PodcastEpisode:
    """Represents a podcast episode for RSS generation"""
    title: str
    description: str
    audio_url: str
    pub_date: datetime
    duration_seconds: int
    file_size: int
    episode_type: str = "full"  # full, trailer, bonus
    season: Optional[int] = None
    episode_number: Optional[int] = None
    guid: Optional[str] = None

@dataclass
class PodcastMetadata:
    """Podcast metadata for RSS feed"""
    title: str
    description: str
    author: str
    email: str
    category: str
    subcategory: str
    language: str = "en-us"
    copyright: str = ""
    website_url: str = ""
    image_url: str = ""
    explicit: bool = False

class RSSGenerator:
    """
    Generates RSS 2.0 compliant XML feeds with iTunes podcast extensions
    """
    
    def __init__(self, podcast_metadata: PodcastMetadata):
        """
        Initialize RSS generator with podcast metadata
        
        Args:
            podcast_metadata: Podcast information and settings
        """
        self.metadata = podcast_metadata
        logger.info(f"RSS Generator initialized for: {podcast_metadata.title}")
    
    def generate_rss_feed(self, episodes: List[PodcastEpisode], 
                         output_path: str = None) -> str:
        """
        Generate complete RSS feed XML
        
        Args:
            episodes: List of podcast episodes to include
            output_path: Optional path to save RSS file
            
        Returns:
            RSS XML as string
        """
        logger.info(f"Generating RSS feed with {len(episodes)} episodes")
        
        # Create RSS root element
        rss = ET.Element("rss")
        rss.set("version", "2.0")
        rss.set("xmlns:itunes", "http://www.itunes.com/dtds/podcast-1.0.dtd")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        
        # Create channel element
        channel = ET.SubElement(rss, "channel")
        
        # Add channel metadata
        self._add_channel_metadata(channel)
        
        # Add episodes
        for episode in episodes:
            self._add_episode_item(channel, episode)
        
        # Generate formatted XML
        xml_string = self._format_xml(rss)
        
        # Save to file if path provided
        if output_path:
            self._save_rss_file(xml_string, output_path)
        
        logger.info(f"RSS feed generated successfully ({len(xml_string)} characters)")
        return xml_string
    
    def _add_channel_metadata(self, channel: ET.Element):
        """Add podcast metadata to channel element"""
        # Required RSS 2.0 elements
        ET.SubElement(channel, "title").text = self.metadata.title
        ET.SubElement(channel, "description").text = self.metadata.description
        ET.SubElement(channel, "link").text = self.metadata.website_url
        ET.SubElement(channel, "language").text = self.metadata.language
        ET.SubElement(channel, "lastBuildDate").text = self._format_rss_date(datetime.now())
        ET.SubElement(channel, "generator").text = "RSS Podcast Digest System v1.0"
        
        # iTunes specific elements
        ET.SubElement(channel, "itunes:title").text = self.metadata.title
        ET.SubElement(channel, "itunes:description").text = self.metadata.description
        ET.SubElement(channel, "itunes:author").text = self.metadata.author
        ET.SubElement(channel, "itunes:language").text = self.metadata.language
        ET.SubElement(channel, "itunes:explicit").text = "yes" if self.metadata.explicit else "no"
        
        # iTunes category
        category = ET.SubElement(channel, "itunes:category")
        category.set("text", self.metadata.category)
        if self.metadata.subcategory:
            subcategory = ET.SubElement(category, "itunes:category")
            subcategory.set("text", self.metadata.subcategory)
        
        # Owner information
        owner = ET.SubElement(channel, "itunes:owner")
        ET.SubElement(owner, "itunes:name").text = self.metadata.author
        ET.SubElement(owner, "itunes:email").text = self.metadata.email
        
        # Podcast image
        if self.metadata.image_url:
            ET.SubElement(channel, "itunes:image").set("href", self.metadata.image_url)
            
            # RSS 2.0 image element
            image = ET.SubElement(channel, "image")
            ET.SubElement(image, "url").text = self.metadata.image_url
            ET.SubElement(image, "title").text = self.metadata.title
            ET.SubElement(image, "link").text = self.metadata.website_url
        
        # Copyright
        if self.metadata.copyright:
            ET.SubElement(channel, "copyright").text = self.metadata.copyright
    
    def _add_episode_item(self, channel: ET.Element, episode: PodcastEpisode):
        """Add episode item to RSS feed"""
        item = ET.SubElement(channel, "item")
        
        # Required elements
        ET.SubElement(item, "title").text = episode.title
        ET.SubElement(item, "description").text = episode.description
        ET.SubElement(item, "pubDate").text = self._format_rss_date(episode.pub_date)
        
        # GUID (globally unique identifier)
        guid_element = ET.SubElement(item, "guid")
        guid_element.text = episode.guid or episode.audio_url
        guid_element.set("isPermaLink", "false" if episode.guid else "true")
        
        # Enclosure (audio file)
        enclosure = ET.SubElement(item, "enclosure")
        enclosure.set("url", episode.audio_url)
        enclosure.set("length", str(episode.file_size))
        enclosure.set("type", "audio/mpeg")
        
        # iTunes specific elements
        ET.SubElement(item, "itunes:title").text = episode.title
        ET.SubElement(item, "itunes:description").text = episode.description
        ET.SubElement(item, "itunes:duration").text = self._format_duration(episode.duration_seconds)
        ET.SubElement(item, "itunes:episodeType").text = episode.episode_type
        
        # Season and episode numbers (if provided)
        if episode.season is not None:
            ET.SubElement(item, "itunes:season").text = str(episode.season)
        if episode.episode_number is not None:
            ET.SubElement(item, "itunes:episode").text = str(episode.episode_number)
    
    def _format_rss_date(self, dt: datetime) -> str:
        """Format datetime for RSS pubDate (RFC 2822)"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.strftime("%a, %d %b %Y %H:%M:%S %z")
    
    def _format_duration(self, seconds: int) -> str:
        """Format duration in HH:MM:SS or MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
    
    def _format_xml(self, root: ET.Element) -> str:
        """Format XML with proper indentation"""
        # Convert to string
        rough_string = ET.tostring(root, encoding='unicode')
        
        # Parse and format with minidom
        parsed = minidom.parseString(rough_string)
        formatted = parsed.toprettyxml(indent="  ", encoding=None)
        
        # Clean up extra whitespace and empty lines
        lines = [line for line in formatted.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def _save_rss_file(self, xml_content: str, file_path: str):
        """Save RSS XML to file"""
        try:
            output_path = Path(file_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(xml_content)
            
            logger.info(f"RSS feed saved to: {output_path}")
            
        except Exception as e:
            logger.error(f"Failed to save RSS file to {file_path}: {e}")
            raise PodcastError(f"Failed to save RSS file: {e}")
    
    def validate_rss_feed(self, xml_content: str) -> bool:
        """
        Validate RSS feed XML structure
        
        Args:
            xml_content: RSS XML content to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            
            # Check root element
            if root.tag != "rss":
                logger.error("Invalid RSS: root element is not 'rss'")
                return False
            
            # Check version
            if root.get("version") != "2.0":
                logger.error("Invalid RSS: version is not '2.0'")
                return False
            
            # Check for channel element
            channel = root.find("channel")
            if channel is None:
                logger.error("Invalid RSS: no channel element found")
                return False
            
            # Check required channel elements
            required_elements = ["title", "description", "link"]
            for element_name in required_elements:
                if channel.find(element_name) is None:
                    logger.error(f"Invalid RSS: missing required element '{element_name}'")
                    return False
            
            # Check items have required elements
            for item in channel.findall("item"):
                item_required = ["title", "description", "enclosure"]
                for element_name in item_required:
                    if item.find(element_name) is None:
                        logger.error(f"Invalid RSS: item missing required element '{element_name}'")
                        return False
                
                # Check enclosure attributes
                enclosure = item.find("enclosure")
                if not all(enclosure.get(attr) for attr in ["url", "length", "type"]):
                    logger.error("Invalid RSS: enclosure missing required attributes")
                    return False
            
            logger.info("RSS feed validation passed")
            return True
            
        except ET.ParseError as e:
            logger.error(f"Invalid RSS: XML parsing error: {e}")
            return False
        except Exception as e:
            logger.error(f"RSS validation error: {e}")
            return False


def create_podcast_metadata(title: str, description: str, author: str, 
                          email: str, category: str = "Technology",
                          subcategory: str = "Tech News", **kwargs) -> PodcastMetadata:
    """Factory function to create podcast metadata"""
    return PodcastMetadata(
        title=title,
        description=description,
        author=author,
        email=email,
        category=category,
        subcategory=subcategory,
        **kwargs
    )


def create_rss_generator(podcast_metadata: PodcastMetadata) -> RSSGenerator:
    """Factory function to create RSS generator"""
    return RSSGenerator(podcast_metadata)


# CLI testing functionality
if __name__ == "__main__":
    import argparse
    from datetime import timedelta
    
    parser = argparse.ArgumentParser(description='RSS Generator CLI')
    parser.add_argument('--test-feed', action='store_true', help='Generate test RSS feed')
    parser.add_argument('--validate', help='Validate RSS feed file')
    parser.add_argument('--output', '-o', help='Output file path')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        if args.test_feed:
            # Create test metadata
            metadata = create_podcast_metadata(
                title="Daily AI & Tech Digest",
                description="Automated daily digest of AI and technology podcast episodes",
                author="Paul Brown",
                email="podcast@paulrbrown.org",
                website_url="https://podcast.paulrbrown.org",
                image_url="https://podcast.paulrbrown.org/artwork.png"
            )
            
            # Create test episodes
            episodes = [
                PodcastEpisode(
                    title="AI News Daily Digest - December 10, 2024",
                    description="Today's top AI developments and breakthroughs",
                    audio_url="https://github.com/McSchnizzle/podscrape2/releases/download/daily-2024-12-10/AI_News_20241210_120000.mp3",
                    pub_date=datetime.now(),
                    duration_seconds=1200,  # 20 minutes
                    file_size=9600000,      # ~9.6MB
                    guid="ai-news-2024-12-10"
                ),
                PodcastEpisode(
                    title="Tech Culture Daily Digest - December 10, 2024", 
                    description="Latest developments in tech culture and industry trends",
                    audio_url="https://github.com/McSchnizzle/podscrape2/releases/download/daily-2024-12-10/Tech_Culture_20241210_120000.mp3",
                    pub_date=datetime.now() - timedelta(hours=1),
                    duration_seconds=900,   # 15 minutes
                    file_size=7200000,      # ~7.2MB
                    guid="tech-culture-2024-12-10"
                )
            ]
            
            # Generate RSS
            generator = create_rss_generator(metadata)
            rss_xml = generator.generate_rss_feed(episodes, args.output)
            
            if not args.output:
                print("Generated RSS Feed:")
                print("-" * 40)
                print(rss_xml)
            
            print(f"✅ Test RSS feed generated successfully")
        
        elif args.validate:
            if not Path(args.validate).exists():
                print(f"❌ File not found: {args.validate}")
                exit(1)
            
            with open(args.validate, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            
            # Create dummy metadata for validation
            metadata = create_podcast_metadata(
                title="Test", description="Test", author="Test", email="test@test.com"
            )
            generator = create_rss_generator(metadata)
            
            if generator.validate_rss_feed(xml_content):
                print(f"✅ RSS feed is valid: {args.validate}")
            else:
                print(f"❌ RSS feed is invalid: {args.validate}")
                exit(1)
        
        else:
            print("Use --help for available commands")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        exit(1)