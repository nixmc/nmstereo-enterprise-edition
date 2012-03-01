#!/usr/bin/env python

import codecs
import json
import pprint
import re
import sys
import urllib

from pymongo import Connection

import settings

# MongoDB
connection = Connection()
store = connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_SPOTIFY_META_COLLECTION")]

# REGEXes
TRACK_REGEX = re.compile(r'\b(?:spotify:track:|http://open.spotify.com/track/)(\S+)\b')

def lookup(id):
    # Lookup id in MongoDB first
    res = store.find_one({"_id": id})
    if not res:
        try:
            res = json.load(urllib.urlopen("http://ws.spotify.com/lookup/1/.json?uri=%s" % urllib.quote(id)))
            res["_id"] = id
            store.save(res)
        except:
            return None
    return res

def extract_track_uris(s):
    ids = list(set(TRACK_REGEX.findall(s)))
    return ["spotify:track:" + id for id in ids]

def lookup_tracks(s):
    tracks = [lookup(track) for track in extract_track_uris(s)]
    return [track for track in tracks if track is not None]

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    # Lookup track
    s = " ".join(sys.argv[1:]) or "spotify:track:6dN6wr1zzbin8Ua8LfqI8G"
    pprint.pprint(lookup_tracks(s))
