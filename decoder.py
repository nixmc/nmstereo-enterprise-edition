#!/usr/bin/env python

import codecs
import json
import pprint
import re
import sys
import urllib

from bson.objectid import ObjectId
import pika
from pymongo import Connection

import settings
import spotify

class Decoder(object):
    """
    Receives DMs, extracts and decodes Spotify URIs, then passes track + 
    requestor details to the broadcaster's 'receive' queue.
    """
    
    timeout = False
    receive_delivery_confirmations = False
    in_queue_declared = False
    out_queue_declared = False
    
    def __init__(self):
        # MongoDB
        self.mongo_connection = Connection()
        self.userstream_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_USERSTREAM_COLLECTION")]
        self.playlist_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_PLAYLIST_COLLECTION")]
        
        # AMQP, get queue names
        self.amqp_in_queue = getattr(settings, "AMQP_MAIN_QUEUE")
        self.amqp_out_queue = getattr(settings, "AMQP_IN_BROADCAST_QUEUE")
        
        # AMQP, async style!
        # Create our connection parameters and connect to RabbitMQ
        parameters = pika.ConnectionParameters(getattr(settings, "AMQP_HOST"))
        self.amqp_connection = pika.SelectConnection(parameters, self.on_connected)
        
        # Add timeout handler (from http://stackoverflow.com/a/8181008)
        if self.timeout:
            self.amqp_connection.add_timeout(60, self.on_timeout)
        
        # Add a callback so we can stop the ioloop
        self.amqp_connection.add_on_close_callback(self.on_closed)        
    
    def start(self):
        # Start our IO/Event loop
        self.amqp_connection.ioloop.start()
    
    def close(self):
        # Gracefully close the connection
        self.amqp_connection.close()
        
        # Loop until we're fully closed, will stop on its own
        self.amqp_connection.ioloop.start()
    
    def on_timeout(self):
        self.amqp_connection.close()
        
    def on_closed(self, frame):
        self.amqp_connection.ioloop.stop()
        
    def on_connected(self, connection):
        # Create a primary channel on our connection passing the on_primary_channel_open callback
        self.amqp_connection.channel(self.on_primary_channel_open)
    
    def on_primary_channel_open(self, ch):
        """
        Fires when the primary channel is available to us.
        """
        # Our usable channel has been passed to us, assign it for future use
        self.amqp_primary_channel = ch
        
        # For receiving confirmations...
        if self.receive_delivery_confirmations:
            self.amqp_primary_channel.confirm_delivery(callback=self.on_delivered, nowait=True)
        
        # Declare 'IN' queue - for receiving items to decode
        self.amqp_primary_channel.queue_declare(queue=self.amqp_in_queue, durable=True,
                                                exclusive=False, auto_delete=False,
                                                callback=self.on_in_queue_declared)
        
        # Declare 'OUT' queue - for sending decoded items to the broadcaster
        self.amqp_primary_channel.queue_declare(queue=self.amqp_out_queue, durable=True,
                                                exclusive=False, auto_delete=False,
                                                callback=self.on_out_queue_declared)
    
    def on_in_queue_declared(self, frame):
        self.in_queue_declared = True
        # Start consuming
        self.amqp_primary_channel.basic_consume(self.on_item, queue=self.amqp_in_queue)
    
    def on_out_queue_declared(self, frame):
        self.out_queue_declared = True
    
    def on_item(self, ch, method, header, body):
        """
        Fires when we receive a new item to decode.
        """
        
        # Lookup data in store, body should actually be an ObjectId        
        item = self.userstream_store.find_one({"_id": ObjectId(body)})
        
        if "direct_message" in item:
            print " [x] Received %r from %r" % (item["direct_message"]["text"], item["direct_message"]["sender"]["screen_name"])
            
            # Any Spotify tracks?
            tracks = spotify.lookup_tracks(item["direct_message"]["text"])
            
            if len(tracks) > 0:
                # Save to playlist
                for track in tracks:
                    id = self.playlist_store.save({'track':track, 'status':'new', 'source':'twitter', 'from':item["direct_message"]["sender"]})
                    # Send each track to the broadcaster's 'receive' queue, so it can be broadcast 
                    # to all connected clients
                    print " [x] Sending %r to broadcaster" % (track['track']['name'],)
                    self.amqp_primary_channel.basic_publish(exchange='',
                                                            routing_key=self.amqp_out_queue,
                                                            body=str(id),
                                                            properties=pika.BasicProperties(
                                                                delivery_mode=2, # make message persistent
                                                            ))
            
            # Confirm delivery
            ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_delivered(self, frame):
        """
        Fires when a message has been delivered.
        """
        pass
    

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    # receiver = DMReceiver()
    # receiver.start_consuming()
    decoder = Decoder()
    
    try:
        print ' [*] Waiting for messages. To exit press CTRL+C'
        decoder.start()
    except KeyboardInterrupt:
        decoder.close()
