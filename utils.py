#!/usr/bin/env python

"""
Misc. utility functions for dealing with tweets, primarily.
"""

import settings

def item_a_direct_message(item):
    """
    Returns True if item appears to be a direct message.
    """
    return "direct_message" in item

def item_a_mention(item):
    """
    Returns True if item appears to be a mention
    """
    if "entities" in item and "user_mentions" in item["entities"]:
        return 0 < len([mention 
                        for mention in item["entities"]["user_mentions"] 
                           if mention["screen_name"] == getattr(settings, "NMSTEREO_SCREEN_NAME", "nmstereo")])

def get_screen_name(item):
    """
    Returns the screen_name from item.
    """
    if item_a_direct_message(item):
        return item["direct_message"]["sender"]["screen_name"]
    elif item_a_mention(item):
        return item["user"]["screen_name"]
    return None

def get_text(item):
    """
    Returns the text from item.
    """
    if item_a_direct_message(item):
        return item["direct_message"]["text"]
    elif item_a_mention(item):
        return item["text"]
    return None

def get_sender(item):
    """
    Returns the sender of the item.
    """
    if item_a_direct_message(item):
        return item["direct_message"]["sender"]
    elif item_a_mention(item):
        return item["user"]
    return None
    
    