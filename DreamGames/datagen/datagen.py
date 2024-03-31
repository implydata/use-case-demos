import yaml
import json
import random
import time
import argparse, sys, logging
import socket
from faker import Faker
from confluent_kafka import Producer
from mergedeep import merge
import sqlite3

# Globals

fake = Faker()
GAMEID = ('G1', 'G2', 'G3')
EVENTTYPE = ('Register', 'Sign In', 'Purchase', 'AdResponse', 'Payment', 'GameProgress', 'Game/device error', 'start Game', 'end Game', 'quit Game')
ADPREFS = ('sports', 'kids', 'clothes', 'dating', 'crypto')

msgCount = 0

# Helper functions

def emit(producer, topic, key, emitRecord):
    global msgCount
    # sid = emitRecord['sid']
    if producer is None:
        print(f'{topic}|{key}|{json.dumps(emitRecord)}')
    else:
        producer.produce(topic, key=str(key), value=json.dumps(emitRecord))
        msgCount += 1
        if msgCount >= 2000:
            producer.flush()
            msgCount = 0
        producer.poll(0)

def emitEvent(p, t, emitRecord):
    emit(p, t, emitRecord["sessionId"], emitRecord)

def emitEventDetail(p, t, k):
    evd = {
        'eventId': k,
        'eventType': EVENTTYPE[int(k)]
    }
    emit(p, t, k, evd)

def emitUserDetail(p, t, k):
    playerdetail = k.split('-')
    ud = {
        'userId': playerdetail[0],
        'playerId': k,
        'userName': fake.user_name(),
        'payingCustomer': fake.random_element(elements=('Y', 'N')),
        'deviceDetail': {
            'deviceId': fake.uuid4(),
            'deviceType': fake.random_element(elements=('mobile', 'desktop')),
            'deviceOS': fake.random_element(elements=('Linux', 'Windows', 'macOS', 'iOS', 'Android')),
            'deviceManufacturer': fake.random_element(elements=('Apple', 'Samsung', 'Huawei', 'Xiaomi', 'Dell', 'HP')),
            'gameVersion': fake.numerify('%.#')
        },
        'playerDemographics': {
            'ageRange': fake.random_element(elements=('18-25', '26-35', '36-50', '51-60', '61+')), 
            'pronouns': fake.random_element(elements=('he/him', 'she/her', 'they/them')),
            'genreOfInterest': fake.random_element(elements=('action', 'strategy', 'casual'))
        },
        'playerAdPreferences': fake.random_sample(ADPREFS)
    }
    emit(p, t, k, ud)

# Read configuration
        
def readConfig(ifn):
    logging.debug(f'reading config file {ifn}')
    with open(ifn, 'r') as f:
        cfg = yaml.load(f, Loader=yaml.FullLoader)
        includecfgs = []
        # get include files if present
        for inc in cfg.get("IncludeOptional", []):
            try:
                logging.debug(f'reading include file {inc}')
                c = yaml.load(open(inc), Loader=yaml.FullLoader)
                includecfgs.append(c)
            except FileNotFoundError:
                logging.debug(f'optional include file {inc} not found, continuing')
        merge(cfg, *includecfgs)
        logging.info(f'Configuration: {cfg}')
        return cfg
                        
            
# --- Main entry point ---
            
def main():

    # Parse command line arguments

    logLevel = logging.INFO
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', help='Enable debug logging', action='store_true')
    parser.add_argument('-q', '--quiet', help='Quiet mode (overrides Debug mode)', action='store_true')
    parser.add_argument('-f', '--config', help='Configuration file for session state machine(s)', required=True)
    # parser.add_argument('-m', '--mode', help='Mode for session state machine(s)', default='default')
    parser.add_argument('-n', '--dry-run', help='Write to stdout instead of Kafka',  action='store_true')
    args = parser.parse_args()

    if args.debug:
        logLevel = logging.DEBUG
    if args.quiet:
        logLevel = logging.ERROR

    logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s', level=logLevel)

    cfgfile = args.config

    config = readConfig(cfgfile)

    if args.dry_run:
        producer = None
    else:
        logging.debug(f'eventTopic: {eventTopic}')

        kafkaconf = config['Kafka']
        kafkaconf['client.id'] = socket.gethostname()
        logging.debug(f'Kafka client configuration: {kafkaconf}')
        producer = Producer(kafkaconf)

    try:
        eventTopic = config['General']['eventTopic']
        eventDetailTopic = config['General']['eventDetailTopic']
        userDetailTopic = config['General']['userDetailTopic']
        gameDetailTopic = config['General']['gameDetailTopic']
        advertiserDetailTopic = config['General']['advertiserDetailTopic']
    except KeyError:
        eventTopic = None    
        eventDetailTopic = None    
        userDetailTopic = None    
        gameDetailTopic = None    
        advertiserDetailTopic = None    

    minSleep = config['General']['minSleep']
    if minSleep is None:
        minSleep = 0.01
    maxSleep = config['General']['maxSleep']
    if maxSleep is None:
        maxSleep = 0.04

    while True:

        tNow = int(time.time())
        
        eventId = str(fake.random_int(min=0, max=9))
        userId = fake.numerify('######')
        playerId = userId + '-' + fake.numerify('###') # convention: playerId is userId-suffix
        ev = {
            'eventId' : eventId,
            'eventTimestamp' : tNow - fake.random_int(min=1, max=100),
            'timestamp' : tNow,
            'gameId' : fake.random_element(elements=GAMEID),
            'userId' : userId,
            'playerId' : playerId,
            'sessionId' : fake.numerify('######'),
            'sessionStatus' : fake.random_element(elements=('start', 'in-progress', 'complete', 'fail')),
            'score' : fake.random_int(min=0, max=100000),
            'gameLevel' : str(fake.random_int(min=1, max=100)),
            'deviceId' : fake.user_agent(),
            'IPaddress' : fake.ipv4(),
            'adId' : fake.word(),
            'adResponse' : fake.random_element(elements=('', 'view', 'click'))
        }
        emitEvent(producer, eventTopic, ev)
        emitEventDetail(producer, eventDetailTopic, eventId)
        emitUserDetail(producer, userDetailTopic, playerId)

        waitSecs = random.uniform(minSleep, maxSleep)
        logging.debug(f'wait time: {waitSecs}')
        time.sleep(waitSecs)

if __name__ == "__main__":
    main()

