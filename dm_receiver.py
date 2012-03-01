#!/usr/bin/env python

import codecs
import json
import re
import sys
import urllib

from bson.objectid import ObjectId
import pika
from pymongo import Connection

import settings
import spotify

class DMReceiver(object):
    def __init__(self):
        # MongoDB
        self.mongo_connection = Connection()
        self.userstream_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_USERSTREAM_COLLECTION")]
        self.playlist_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_PLAYLIST_COLLECTION")]
        
        # AMPQ
        self.ampq_queue = getattr(settings, "AMPQ_QUEUE")
        self.ampq_connection = pika.BlockingConnection(pika.ConnectionParameters(
                host=getattr(settings, "AMPQ_HOST")))
        self.ampq_channel = self.ampq_connection.channel()
        self.ampq_channel.queue_declare(queue=self.ampq_queue, durable=True)
    
    def start_consuming(self):
        self.ampq_channel.basic_consume(self.receive, queue=self.ampq_queue)
        self.ampq_channel.start_consuming()
    
    def receive(self, ch, method, properties, message):
        print " [x] Received %r" % (message,)
        
        # Lookup data in store, message should actually be an ObjectId        
        item = self.userstream_store.find_one({"_id": ObjectId(message)})
        
        if "direct_message" in item:
            print "> from", item["direct_message"]["sender"]["screen_name"], ":", item["direct_message"]["text"]
            
            # Any Spotify tracks?
            tracks = spotify.lookup_tracks(item["direct_message"]["text"])
            
            if len(tracks) > 0:
                # Save to playlist
                for track in tracks:
                    id = self.playlist_store.save({'track':track, 'status':'new', 'from':item["direct_message"]["sender"]})
                    # Send each track to 'queue' queue, so it can be broadcast 
                    # to connected clients
                    
                    
            
            ch.basic_ack(delivery_tag=method.delivery_tag)
    

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    receiver = DMReceiver()
    print ' [*] Waiting for messages. To exit press CTRL+C'
    receiver.start_consuming()
