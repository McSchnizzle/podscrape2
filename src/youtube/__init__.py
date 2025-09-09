"""
YouTube integration module for channel management and video discovery.
"""

from .channel_resolver import ChannelResolver, ChannelInfo, resolve_channel, validate_channel_id

__all__ = ['ChannelResolver', 'ChannelInfo', 'resolve_channel', 'validate_channel_id']