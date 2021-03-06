# https://en.bitcoin.it/wiki/Controlled_supply
# get block height
# https://blockchain.info/q/getblockcount

# calculate progress:
# halving_constant = 840,000
# last_event = 210,000
# next_event = last_height + halving_constant
# blockheight = https://blockchain.info/q/getblockcount
# progress = ( blockheight / next_event ) * 100
# if progress > 100, update last_event, update next_event
# this twitter bot can finally rest once we have reached the 34th reward era.
# publish a tweet everytime progress has increased by a full percentage
import os
import json
import math
import requests
import tweepy
import boto3

# AWS SSM
client = boto3.client('ssm')

# keys
access_token = os.environ['twitter_access_token']
access_token_secret = os.environ['twitter_access_token_secret']
consumer_key = os.environ['twitter_api_key']
consumer_secret = os.environ['twitter_api_secret']
# LTC defined constant: n blocks bewteen halving events
SUBSIDY_HALVING_INTERVAL = 210000

# For now, depend on blockcypher.com for getting latest block height
GET_BLOCK_HEIGHT = "https://api.blockcypher.com/v1/ltc/main"

# initial ltc mining reward
INIT_MINING_SUBSIDY = 50

t_auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
t_auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(t_auth)

def calc_progress(blockheight, next_event, SUBSIDY_HALVING_INTERVAL):
    # return value between 0 - 1
    return ( 1 - (next_event - blockheight) / SUBSIDY_HALVING_INTERVAL )

def get_block_height_from_last_event(current_block_height, SUBSIDY_HALVING_INTERVAL):
    # determine the block height of the last halving event
    # get currernt blockheight
    # divide it by the constant to determine how many events have occured
    # events * constant = block height of last event
    n_events = current_block_height / SUBSIDY_HALVING_INTERVAL
    last_event_block_height = math.floor(n_events) * SUBSIDY_HALVING_INTERVAL
    return last_event_block_height

def blocks_until_next_event(next_event, current_block_height):
    return next_event - current_block_height

def calc_reward_era(current_block_height, n_block_to_halve):
    # calcualte the reward era we are currently in. + 1 to account for the 0th block reward
    return math.floor((current_block_height / n_block_to_halve) + 1)

def calc_block_reward(reward_era):
    #
    return INIT_MINING_SUBSIDY / (2**(reward_era-1))

def get_block_height():
    r = requests.get(GET_BLOCK_HEIGHT)
    return int(r.text)

def gen_progress_string(progress):
    # progress: type: float 0.0 - 1.0
    # ░
    # ▒
    # ▓
    # █
    # ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    # ┃ ████████░░░░░░░░░░░ 48%  ┃
    # ┗━━━━━━━━━━━━━━━━━━━━━━━━━━┛
    # 20 * progress
    # ▓░░░░░░░░░░░░░░
    bar_length = 15
    c = bar_length * progress
    p = math.floor(c)
    f = (progress * 100) % (100 / bar_length)

    bar = map(lambda x:'█', range(p))
    bar = ''.join(bar)

    # if 0 < f and f < 1:
    #     bar = bar + "░"
    #     pass
    # elif 1 <= f and f < 2.5:
    #     bar = bar + "▒"
    #     pass
    # elif 2.5 <= f and f < 4:
    #     bar = bar + "▓"
    #     pass

    bar_empty = ''.join( map( lambda x:'░', range(bar_length - p) ) )
    bar = ''.join( [bar, bar_empty] )
    progress_string = str(math.floor(progress * 100))
    bar = ''.join([ bar, " ", progress_string, "%" ])

    return bar

def update_status(status):
    response = api.update_status(status)
    print(response)
    return response

def get_tweets():
    return

def run(event="", context="", publish=True):
    # get the current block height from blockchain.info
    CURRENT_BLOCK_HEIGHT = get_block_height()
    # determine which blockheight the last halving event occured
    LAST_EVENT = get_block_height_from_last_event(CURRENT_BLOCK_HEIGHT, SUBSIDY_HALVING_INTERVAL)
    # determine which reward era we are in
    REWARD_ERA = calc_reward_era(CURRENT_BLOCK_HEIGHT, SUBSIDY_HALVING_INTERVAL)
    # determine the target blockheight for the next halving event
    NEXT_EVENT = LAST_EVENT + SUBSIDY_HALVING_INTERVAL
    # calculate current progress towards reaching the next halving event 0 - 1
    PROGRESS = calc_progress(CURRENT_BLOCK_HEIGHT, NEXT_EVENT, SUBSIDY_HALVING_INTERVAL)
    # post to twitter only if progress has increased by a full percentage since the last tweet
    BLOCK_REWARD = calc_block_reward(REWARD_ERA)
    # remaining blocks until next event
    BLOCKS_LEFT = blocks_until_next_event(NEXT_EVENT, CURRENT_BLOCK_HEIGHT)

    print('current block height: ', CURRENT_BLOCK_HEIGHT)
    print('last event: ', LAST_EVENT)
    print('reward era: ', REWARD_ERA)
    print('next event: ', NEXT_EVENT)
    print('progress: ', PROGRESS * 100)
    print('block reward: ', BLOCK_REWARD, 'BTC')
    print('remaining blocks: ', BLOCKS_LEFT)
    status = gen_progress_string(PROGRESS)
    status = "".join([
        'Reward Era: ', str(REWARD_ERA), '\n',
        'Block Reward: ', str(BLOCK_REWARD), '\n',
        'Blocks Left: ', str(BLOCKS_LEFT), '\n',
        status
    ])


    # get the previously computed value from storage
    ssm_tagValue = int(PROGRESS * 100)
    ssm_get_response = client.get_parameter(
        Name='/BitcoinProgress/lastKnownPercentage',
        WithDecryption=False
    )
    # check if the newly computed value is different from the previous
    diff = ssm_get_response['Parameter']['Value'].find(str(ssm_tagValue))
    print('diff', diff)
    if publish == True and diff == -1:
        # update the value
        ssm_response = client.put_parameter(
            Name='/BitcoinProgress/lastKnownPercentage',
            Description='',
            Value=str(ssm_tagValue),
            Type='String',
            Overwrite=True
        )
        # publish
        body = { "message": update_status(status), "tagValue": ssm_tagValue, "published": True }
        pass
    else:
        body = { "message": status, "tagValue": ssm_tagValue, "published": False }
        pass

    response = {
        "statusCode": 200,
        "body": json.dumps(body)
    }

    print(status)
    return response