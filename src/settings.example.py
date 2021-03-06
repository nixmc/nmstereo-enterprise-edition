# MongoDB stuff...
MONGODB_DB_NAME = "nmstereo"
MONGODB_USERSTREAM_COLLECTION = "nmstereo_userstream"
MONGODB_PLAYLIST_COLLECTION = "nmstereo_playlist"
MONGODB_SPOTIFY_META_COLLECTION = "nmstereo_spotify_meta"

# AMQP stuff...
AMQP_HOST = "localhost"
AMQP_MAIN_QUEUE = "decode"
AMQP_IN_BROADCAST_QUEUE = "receive"
AMQP_CONFIRM_BROADCAST_QUEUE = "confirm"
# AMQP_OUT_BROADCAST_QUEUE = "broadcast"
AMQP_BROADCAST_EXCHANGE = "tracks"

# OAuth stuff...
OAUTH_CONSUMER_KEY = ""
OAUTH_CONSUMER_SECRET = ""
OAUTH_ACCESS_KEY = ""
OAUTH_ACCESS_SECRET = ""

# Other config options...
NMSTEREO_SCREEN_NAME = "nmstereo"
NMSTEREO_SEND_TWEETS = False