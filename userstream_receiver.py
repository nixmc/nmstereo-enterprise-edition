#!/usr/bin/env python

import codecs
import sys
import json

import tweepy
import pika
from pymongo import Connection

import settings

class StreamListener(tweepy.StreamListener):
    def __init__(self):
        super(tweepy.StreamListener, self).__init__()
        
        # MongoDB
        self.mongo_connection = Connection()
        self.store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_USERSTREAM_COLLECTION")]
        
        # AMPQ
        self.ampq_queue = getattr(settings, "AMPQ_QUEUE")
        self.ampq_connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=getattr(settings, "AMPQ_HOST")))
        self.channel = self.ampq_connection.channel()
        self.channel.queue_declare(queue=self.ampq_queue, durable=True)
    
    def on_data(self, data):
        if not data:
            return True
        
        # Decode JSON data
        item = json.loads(data)
        
        # Save data
        id = self.store.save(item)
        
        # Process further, if a DM
        if "direct_message" in item:
            print "> from", item["direct_message"]["sender"]["screen_name"], ":", item["direct_message"]["text"]
            self.channel.basic_publish(exchange='',
                routing_key=self.ampq_queue,
                body=str(id),
                properties=pika.BasicProperties(
                    delivery_mode=2, # make message persistent
            ))
        
        return True
    
    def on_status(self, status):
        return True
    
    def on_error(self, status_code):
        return True  # keep stream alive

    def on_timeout(self):
        return True

    def on_delete(self, status_id, user_id):
        return True

    def on_limit(self, track):
        return True


if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    # Create an auth handler
    auth = tweepy.OAuthHandler(getattr(settings, "OAUTH_CONSUMER_KEY"), getattr(settings, "OAUTH_CONSUMER_SECRET"))
    auth.set_access_token(getattr(settings, "OAUTH_ACCESS_KEY"), getattr(settings, "OAUTH_ACCESS_SECRET"))
    
    # Connect to stream
    stream = tweepy.Stream(auth, StreamListener(), secure=True)
    stream.userstream()
