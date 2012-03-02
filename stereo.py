#!/usr/bin/env python

"""
Plays incoming tracks on the stereo. Tells the broadcaster when a track has been received and is playing. 
"""

import codecs
import pprint
import sys

import pika

import settings

class Stereo(object):
    """
    Receives tracks from the broadcaster, and plays them.
    
    Notifies the broadcaster when it has started playing a track.
    """
    
    timeout = False
    receive_delivery_confirmations = False
    
    def __init__(self):
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
        
        The primary channel is to receive new items to be queued, and to broadcast
        items to be played.
        """
        pass
        
    def on_in_queue_declared(self, frame):
        # Start consuming
        self.amqp_primary_channel.basic_consume(self.on_item, queue=self.amqp_in_queue)
    
    def on_item(self, ch, method, header, track):
        """
        Fires when we receive a new track to play.
        """
        print "Got ", track
        
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
    