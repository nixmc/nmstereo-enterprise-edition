#!/usr/bin/env python

"""
Picks up requests from the playlist, and broadcasts to all connected clients (over XMPP?).
"""

import codecs
import pprint
import sys

from bson.objectid import ObjectId
import pika
from pymongo import Connection

import settings

class Broadcaster(object):
    """
    Receives items, sets their status to 'queued', plays them in order when
    at least 1 client is connected
    """
    
    receive_delivery_confirmations = False
    
    def __init__(self):
        # MongoDB
        self.mongo_connection = Connection()
        self.playlist_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_PLAYLIST_COLLECTION")]
        
        # Load previously queued items
        self.items = [item for item in self.playlist_store.find({'status': 'queued'})]
        
        # AMQP, get queue names
        self.amqp_in_queue = getattr(settings, "AMQP_IN_BROADCAST_QUEUE")
        self.amqp_out_queue = getattr(settings, "AMQP_OUT_BROADCAST_QUEUE")
        self.amqp_confirm_queue = getattr(settings, "AMQP_CONFIRM_BROADCAST_QUEUE")
        
        # AMQP, async style!
        # Create our connection parameters and connect to RabbitMQ
        parameters = pika.ConnectionParameters(getattr(settings, "AMQP_HOST"))
        self.amqp_connection = pika.SelectConnection(parameters, self.on_connected)
        
        # Add timeout handler (from http://stackoverflow.com/a/8181008)
        self.amqp_connection.add_timeout(60, self.on_timeout)
        
        # Add a callback so we can stop the ioloop
        self.amqp_connection.add_on_close_callback(self.on_closed)        
    
    def start(self):
        # Start our IO/Event loop
        self.amqp_connection.ioloop.start()
    
    def close(self):
        print "Closing"
        # Gracefully close the connection
        self.amqp_connection.close()
        
        # Loop until we're fully closed, will stop on its own
        self.amqp_connection.ioloop.start()
    
    def send(self):
        # Get next item
        self.current_item = self.items.pop(0)
        
        # Send item
        print "> Sending", self.current_item['track']['track']['name']
        self.amqp_primary_channel.basic_publish(exchange='',
                                        routing_key=self.amqp_out_queue,
                                        body=str(self.current_item['_id']),
                                        properties=pika.BasicProperties(
                                          content_type="text/plain",
                                          delivery_mode=2))
        
        # Mark item as sent
        self.current_item['status'] = 'sent'
        # TODO
        # ...
        # self.playlist_store.update({'_id': self.current_item['_id']}, self.current_item)
    
    def next(self):
        pass
    
    def on_timeout(self):
        self.amqp_connection.close()
    
    def on_closed(self, frame):
        print "Stopping the ioloop"
        self.amqp_connection.ioloop.stop()
    
    def on_connected(self, connection):
        # Create a primary channel on our connection passing the on_primary_channel_open callback
        self.amqp_connection.channel(self.on_primary_channel_open)
        
        # Also create a secondary channge, passing the on_seconday_channel_open callback
        self.amqp_connection.channel(self.on_secondary_channel_open)
    
    def on_primary_channel_open(self, ch):
        # Our usable channel has been passed to us, assign it for future use
        self.amqp_primary_channel = ch
        
        # For receiving confirmations...
        if self.receive_delivery_confirmations:
            self.amqp_primary_channel.confirm_delivery(callback=self.on_delivered, nowait=True)
        
        # Declare 'IN' queue - for receiving items to queue
        self.amqp_primary_channel.queue_declare(queue=self.amqp_in_queue, durable=True,
                                        exclusive=False, auto_delete=False,
                                        callback=self.on_in_queue_declared)
        
        # Declare 'OUT' queue - for broadcasting items
        self.amqp_primary_channel.queue_declare(queue=self.amqp_out_queue, durable=True,
                                        exclusive=False, auto_delete=False,
                                        callback=self.on_out_queue_declared)
    
    def on_secondary_channel_open(self, ch):
        # Our usable channel has been passed to us, assign it for future use
        self.amqp_secondary_channel = ch
        
        # Declare 'IN' queue - for receiving confirmations
        self.amqp_secondary_channel.queue_declare(queue=self.amqp_confirm_queue, durable=True,
                                        exclusive=False, auto_delete=False,
                                        callback=self.on_confirm_queue_declared)

    def on_in_queue_declared(self, frame):
        # Start consuming
        self.amqp_primary_channel.basic_consume(self.on_item, queue=self.amqp_in_queue)
    
    def on_confirm_queue_declared(self, frame):
        # Start consuming
        self.amqp_secondary_channel.basic_consume(self.on_confirmation, queue=self.amqp_confirm_queue)
    
    def on_out_queue_declared(self, frame):
        # If no items 'sent' or 'playing', broadcast next item in queue
        if len(self.items) > 0:
            items = [item for item in self.playlist_store.find({'$or': [{'status':'sent'},{'status':'playing'}]})]
            if len(items) == 0:
                # Send next item in queue
                self.send()
    
    def on_item(self, ch, method, header, body):
        print body
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_confirmation(self, ch, method, header, body):
        print body
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_delivered(self, frame):
        print "Delivered! :)", type(message)
    

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    broadcaster = Broadcaster()
    pprint.pprint(broadcaster.items)
    
    try:
        broadcaster.start()
    except KeyboardInterrupt:
        broadcaster.close()
