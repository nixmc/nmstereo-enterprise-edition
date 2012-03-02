#!/usr/bin/env python

"""
Picks up requests from the playlist, and broadcasts to all connected clients.
"""

import codecs
import datetime
import json
import pprint
import sys
from threading import Timer

from bson.objectid import ObjectId
import pika
from pymongo import Connection
import twitter

import settings

class Broadcaster(object):
    """
    Receives items, sets their status to 'queued', plays them in order when
    at least 1 client is connected.
    """
    
    timeout = False
    items = []
    current_item = None
    receive_delivery_confirmations = False
    
    def __init__(self):
        # Twitter client
        self.twitter = twitter.Twitter(api_version='1', 
                                       auth=twitter.oauth.OAuth(getattr(settings, "OAUTH_ACCESS_KEY"), 
                                                                getattr(settings, "OAUTH_ACCESS_SECRET"), 
                                                                getattr(settings, "OAUTH_CONSUMER_KEY"), 
                                                                getattr(settings, "OAUTH_CONSUMER_SECRET")))
        
        # MongoDB
        self.mongo_connection = Connection()
        self.playlist_store = self.mongo_connection[getattr(settings, "MONGODB_DB_NAME")][getattr(settings, "MONGODB_PLAYLIST_COLLECTION")]
        
        # Load previously queued items
        self.items = [item for item in self.playlist_store.find({'status': 'queued'})]
        
        # Load 'playing' or 'sent' items -- there should be only ONE!
        self.current_item = self.playlist_store.find_one({'$or': [{'status':'sent'},{'status':'playing'}]})        
        
        # AMQP, get queue names
        self.amqp_in_queue = getattr(settings, "AMQP_IN_BROADCAST_QUEUE")
        self.amqp_confirm_queue = getattr(settings, "AMQP_CONFIRM_BROADCAST_QUEUE")
        
        # AMQP, get exchange names
        self.amqp_broadcast_exchange = getattr(settings, "AMQP_BROADCAST_EXCHANGE")
        
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
    
    def send(self):
        """
        Broadcasts the next item to all interested parties.
        """
        
        # Check that we have something to send
        if len(self.items) > 0:
            
            # If no items 'sent' or 'playing', send next item in queue
            sent_items = [item for item in self.playlist_store.find({'status':'sent'})]
            playing_items = [item for item in self.playlist_store.find({'status':'playing'})]
            
            # Look for any expired items in playing
            expired = False
            for item in playing_items:
                end_date = item['start_date'] + datetime.timedelta(seconds=item['track']['track']['length'])
                expired = expired or end_date < datetime.datetime.now()
            
            # Assume we send nothing
            send_item = False
            # Conditions under which we send...
            # 1. Nothing sent, and nothing playing
            send_item = send_item or (len(sent_items) == 0 and len(playing_items) == 0)
            # 2. Nothing sent, and something expired marked as playing
            send_item = send_item or (len(sent_items) == 0 and len(playing_items) > 0 and expired)
            
            if send_item:
                
                # Send next item in queue
                self.current_item = self.items.pop(0)
                print " [x] Sending %r" % (self.current_item['track']['track']['name'],)
                
                # Send using the broadcast exchange (Pub/Sub)
                self.amqp_primary_channel.basic_publish(exchange=self.amqp_broadcast_exchange,
                                                        routing_key='',
                                                        body=json.dumps({'_id': str(self.current_item['_id']),
                                                                         'track': self.current_item['track'],
                                                                         'from': self.current_item['from']}),
                                                        properties=pika.BasicProperties(
                                                          content_type="application/json",
                                                          delivery_mode=2))
                
                # Mark item as sent
                self.current_item['status'] = 'sent'
                self.playlist_store.update({'_id': self.current_item['_id']}, self.current_item)
    
    def next(self):
        print " [x] Next!"
        
        # Set current item to played
        self.current_item['status'] = 'played'
        self.playlist_store.update({'_id': self.current_item['_id']}, self.current_item)
        
        # Play next item
        self.send()
                
    def now_playing(self, id):
        # Override current item with this id
        self.current_item = self.playlist_store.find_one({'_id': ObjectId(id)})
        
        # Mark existing 'playing' items as 'played'
        for item in self.playlist_store.find({'status':'playing'}):
            item['status'] = 'played'
            self.playlist_store.update({'_id': item['_id']}, item)
        
        # Mark current item as 'playing', set start_time
        self.current_item['status'] = 'playing'
        self.current_item['start_date'] = datetime.datetime.now()
        self.playlist_store.update({'_id': self.current_item['_id']}, self.current_item)
        
        # Set up timer to fire at the end of the current item
        timer = Timer(self.current_item['track']['track']['length'], self.next)
        timer.start()
        
        # Tweet!
        track_name = self.current_item['track']['track']['name']
        artist_name = self.current_item['track']['track']['artists'][0]['name']
        screen_name = self.current_item['from']['screen_name']
        msg = '#Nowplaying %s / %s, requested by @%s' % (artist_name, track_name, screen_name)
        self.twitter.statuses.update(status=msg, lat="50.82519295639108", long="-0.14594435691833496", display_coordinates=True)
        
    
    def on_timeout(self):
        self.amqp_connection.close()
    
    def on_closed(self, frame):
        self.amqp_connection.ioloop.stop()
    
    def on_connected(self, connection):
        # Create a primary channel on our connection passing the on_primary_channel_open callback
        self.amqp_connection.channel(self.on_primary_channel_open)
        
        # Also create a secondary channge, passing the on_seconday_channel_open callback
        self.amqp_connection.channel(self.on_secondary_channel_open)
    
    def on_primary_channel_open(self, ch):
        """
        Fires when the primary channel is available to us.
        
        The primary channel is to receive new items to be queued, and to broadcast
        items to be played.
        """
        # Our usable channel has been passed to us, assign it for future use
        self.amqp_primary_channel = ch
        
        # For receiving confirmations...
        if self.receive_delivery_confirmations:
            self.amqp_primary_channel.confirm_delivery(callback=self.on_delivered, nowait=True)
        
        # Declare 'IN' queue - for receiving items to queue
        self.amqp_primary_channel.queue_declare(queue=self.amqp_in_queue, durable=True,
                                                exclusive=False, auto_delete=False,
                                                callback=self.on_in_queue_declared)
        
        # Declare 'fanout' exchange - for broadcasting items
        # The fanout exchange is very simple. It just broadcasts all the
        # messages it receives to all the queues it knows.
        self.amqp_primary_channel.exchange_declare(exchange=self.amqp_broadcast_exchange, type='fanout',
                                                   callback=self.on_exchange_declared)
        
    def on_secondary_channel_open(self, ch):
        """
        Fires when the secondary channel is available to us.
        
        We declare a secondary channel so we can receive confirmations from
        a seperate channel.
        """
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
    
    def on_exchange_declared(self, frame):
        # If no items 'sent' or 'playing', broadcast next item in queue
        self.send()
    
    def on_item(self, ch, method, header, body):
        """
        Fires when we receive a new item to queue.
        """
        # Get the item from the playlist store
        item = self.playlist_store.find_one({'_id': ObjectId(body)})
        print " [x] Received %r" % (item['track']['track']['name'],)
        
        # Add item to our list
        self.items.append(item)
        
        # Mark item as 'queued'
        item['status'] = 'queued'
        self.playlist_store.update({'_id': item['_id']}, item)
        
        # If no items 'sent' or 'playing', broadcast next item in queue
        self.send()
        
        # Acknowledge
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_confirmation(self, ch, method, header, body):
        """
        Fires when a message has been received. Clients are responsible for 'firing' this by 
        publishing to the `self.amqp_confirm_queue` queue.
        """
        print " [x] Received confirmation %r" % (body,)
        self.now_playing(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_delivered(self, frame):
        """
        Fires when a message has been delivered.
        """
        pass
    

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    broadcaster = Broadcaster()
    # pprint.pprint(broadcaster.items)
    
    try:
        print ' [*] Waiting for messages. To exit press CTRL+C'
        broadcaster.start()
    except KeyboardInterrupt:
        broadcaster.close()
