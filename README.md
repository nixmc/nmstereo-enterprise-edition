# @nmstereo -- enterprise edition

## Crowd-sourcing the office stereo with Twitter and Spotify

## About

Meet @[nmstereo](http://twitter.com/nmstereo) - our social office stereo 'bot,
 responsible for crowd-sourcing what gets played on our office stereo, with
 help from Twitter, Spotify and generous sprinklings of pixie dust!

## How to build your own

1. Grab yourself:

* A Twitter account, such as @[nmstereo](http://twitter.com/nmstereo).
* A (preferably) Linux server running: 
** [Python](http://www.python.org/) 2.6+
** [RabbitMQ](http://www.rabbitmq.com/)
** [MongoDB](http://www.mongodb.org/)
** [virtualenv](http://www.virtualenv.org/) (optional, but recommended)
** [pip](http://www.pip-installer.org/) (optional, but recommended)
* An OS X box running:
** [Spotify](http://www.spotify.com/)
* A copy of [the source code](https://github.com/nixmc/nmstereo-enterprise-edition).

2. On your Linux server:

2.1 Create a new virtualenv, activate it, and install the requirements listed in [requirements.txt](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/requirements.txt):

<pre>
    $ virtualenv --no-site-packages ENV
    $ source ENV/bin/activate
    $ pip install requirements.txt
</pre>

2.2 Grant "Read, Write and Direct Messages" permissions to your designated Twitter account. 

2.3 Make a [settings.py](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/settings.example.py), and edit the settings to match your own environment.

2.4 Run the [receiver](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/userstream_receiver.py), [decoder](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/decoder.py) and [broadcaster](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/broadcaster.py):

<pre>
    $ userstream_receiver.py
    $ decoder.py
    $ broadcaster.py
</pre>

3. On your OS X box:

3.1 Create a new virtualenv, activate it, and install the requirements listed in [requirements.txt](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/requirements.txt):

<pre>
    $ virtualenv --no-site-packages ENV
    $ source ENV/bin/activate
    $ pip install requirements.txt
</pre>

3.2 Make a [settings.py](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/settings.example.py), and edit the settings to match your own environment.

3.3 Run the [stereo](https://github.com/nixmc/nmstereo-enterprise-edition/blob/master/src/stereo.py) client:

<pre>
    $ stereo.py
</pre>

4. Invite your friends to "Get their hits out"! :)

## Roadmap

* Frictionless deployment on Linux and OS X
* Compatibility with [Raspberry Pi](http://www.raspberrypi.org/)
* Compatibility with [Mopidy](https://github.com/mopidy/mopidy)
* Integration with Spotify's [AppleScript library](http://developer.spotify.com/blog/archives/2011/05/27/spotify-051-for-mac-%E2%80%94-now-with-applescript-support/)

## Contact

For more info, contact:

* devden [at] nixonmcinnes.co.uk