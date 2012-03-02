#!/usr/bin/env python

"""
Plays incoming tracks on the stereo. Tells the broadcaster when a track has been received and is playing. 
"""

import codecs
import json
import pprint
import subprocess
import sys

import pika

import settings

class Stereo(object):
    """
    Receives tracks from the broadcaster, and plays them.
    
    Notifies the broadcaster when it has started playing a track.
    """
    
    timeout = False
    out_queue_declared = False
    receive_delivery_confirmations = False
    
    def __init__(self):
        
        # AMQP, get queue names
        self.amqp_out_queue = getattr(settings, "AMQP_CONFIRM_BROADCAST_QUEUE")
        
        # AMQP, get exchange to connect to
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
    
    def play(self, track):
        """
        Play the requested track.
        """
        # Grab the URI
        uri = track['track']['track']['href']
        
        # Play it
        print " [x] Playing %r" % (uri,)
        subprocess.call(('open', '-g', '/Applications/Spotify.app', uri))
        
        # Send confirmation to the broadcaster
        self.amqp_primary_channel.basic_publish(exchange='',
                                                routing_key=self.amqp_out_queue,
                                                body=str(track['_id']),
                                                properties=pika.BasicProperties(
                                                    delivery_mode=2, # make message persistent
                                                ))
    
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
        
        # Declare 'fanout' exchange - for receiving items from the broadcaster
        self.amqp_primary_channel.exchange_declare(exchange=self.amqp_broadcast_exchange, type='fanout',
                                                   callback=self.on_exchange_declared)
        
        # Declare 'OUT' queue - for sending confirmations back to the broadcaster
        self.amqp_primary_channel.queue_declare(queue=self.amqp_out_queue, durable=True,
                                                exclusive=False, auto_delete=False,
                                                callback=self.on_out_queue_declared)

    
    def on_exchange_declared(self, frame):
        self.amqp_primary_channel.queue_declare(exclusive=True, callback=self.on_in_queue_declared)
    
    def on_in_queue_declared(self, frame):
        # Get the name of the queue
        self.amqp_in_queue = frame.method.queue
        
        # Bind the queue to our broadcast channel
        self.amqp_primary_channel.queue_bind(exchange=self.amqp_broadcast_exchange,
                                             queue=self.amqp_in_queue)
        
        # Start consuming
        self.amqp_primary_channel.basic_consume(self.on_item, queue=self.amqp_in_queue)
    
    def on_out_queue_declared(self, frame):
        self.out_queue_declared = True
    
    def on_item(self, ch, method, header, track):
        """
        Fires when we receive a new track to play.
        """
        self.track = json.loads(track)
        print " [x] Received %r" % (self.track['track']['track']['name'],)
        
        self.play(self.track)
        
        # Acknowledge
        ch.basic_ack(delivery_tag=method.delivery_tag)
    
    def on_delivered(self, frame):
        """
        Fires when a message has been delivered.
        """
        pass
    

if __name__ == "__main__":
    # Write UTF-8 to stdout
    sys.stdout = codecs.getwriter('utf8')(sys.stdout)
    
    stereo = Stereo()
    
    try:
        print ' [*] Waiting for tracks. To exit press CTRL+C'
        stereo.start()
    except KeyboardInterrupt:
        stereo.close()
    