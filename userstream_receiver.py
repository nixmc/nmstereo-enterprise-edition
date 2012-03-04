#!/usr/bin/env python

import codecs
import httplib
import ssl
import sys
import time
import json

import tweepy
import pika
from pymongo import Connection

import settings
import utils

class StreamListener(tweepy.StreamListener):
    """
    Receives the entire userstream. Forwards DMs to the Decoder.
    """
    
    def __init__(self):
        super(tweepy.StreamListener, self).__init__()
        
        self.screen_name = getattr(settings, "NMSTEREO_SCREEN_NAME", "nmstereo")
        
        # MongoDB
        self.mongo_connection = Connection()
        self.store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_USERSTREAM_COLLECTION")]
        
        # AMQP
        self.amqp_queue = getattr(settings, "AMQP_MAIN_QUEUE")
        self.amqp_connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=getattr(settings, "AMQP_HOST")))
        self.channel = self.amqp_connection.channel()
        self.channel.queue_declare(queue=self.amqp_queue, durable=True)
    
    def on_data(self, data):
        if not data:
            return True
        
        # Decode JSON data
        item = json.loads(data)
        
        # Save data
        id = self.store.save(item)
        
        # Is this item a direct message?
        a_direct_message = utils.item_a_direct_message(item)
        
        # Is this item a mention?
        a_mention = utils.item_a_mention(item)
            
        # Continue processing further down the chain
        if a_direct_message or a_mention:
            print " [x] Received", utils.get_screen_name(item), ":", utils.get_text(item)
            self.channel.basic_publish(exchange='',
                routing_key=self.amqp_queue,
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
    err_count = 0
    while True:
        try:
            print ' [*] Connecting. To exit press CTRL+C'
            stream.userstream()
        except httplib.IncompleteRead, e:
            print e
            err_count += 1
        except ssl.SSLError, e:
            print e
            err_count += 1
        except KeyboardInterrupt:
            stream.disconnect()
            sys.exit()
            
        time.sleep(5)

        if err_count > 4:
            print "5 errors, quitting"
            exit()
