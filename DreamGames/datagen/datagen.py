import yaml
import json
import random
import time
import argparse, sys, logging
import socket
from faker import Faker
from confluent_kafka import Producer
from collections import OrderedDict
from mergedeep import merge
import sqlite3

# Globals

fake = Faker()
GAMEID = ('G1', 'G2', 'G3')
EVENTTYPE = ('Register', 'Sign In', 'Purchase', 'AdResponse', 'Payment', 'GameProgress', 'Game/device error', 'start Game', 'end Game', 'quit Game')
ADPREFS = ('sports', 'kids', 'clothes', 'dating', 'crypto')

# the index into SESSIONSTATUS is the anomaly mode
SESSIONSTATUS = {
    False: OrderedDict([
      ('start', 0.1),
      ('in-progress', 0.8),
      ('complete', 0.07),
      ('fail', 0.03)
    ]),
    True: OrderedDict([
      ('start', 0.1),
      ('in-progress', 0.6),
      ('complete', 0.07),
      ('fail', 0.23)
    ])
}
REVENUEPARAM = {
    False: { 'mu': 20.0, 'sigma': 4.0 },
    True:  { 'mu': 10.0, 'sigma': 2.5 }
}
ADRESPONSE = OrderedDict([
    ('',             0.85),
    ('Impression',   0.07),
    ('Click',        0.05),
    ('Registration', 0.03)
])
OSPLATFORM = OrderedDict([
    ('Linux',   0.03), 
    ('Windows', 0.14),
    ('macOS',   0.11),
    ('iOS',     0.34),
    ('Android', 0.38)
])
PLAYERAGE = OrderedDict([
    ('18-25', 0.56), 
    ('26-35', 0.20),
    ('36-50', 0.10),
    ('51-60', 0.10),
    ( '61+',  0.04)
])

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
        kafkaconf = config['Kafka']
        kafkaconf['client.id'] = socket.gethostname()
        logging.debug(f'Kafka client configuration: {kafkaconf}')
        producer = Producer(kafkaconf)

    try:
        eventTopic = config['General']['eventTopic']
        logging.debug(f'eventTopic: {eventTopic}')
    except KeyError:
        eventTopic = None    

    minSleep = config['General']['minSleep']
    if minSleep is None:
        minSleep = 0.01
    maxSleep = config['General']['maxSleep']
    if maxSleep is None:
        maxSleep = 0.04

    logging.debug(f'Generating {config['General']['maxUsers']} users')
    users = [{
        'deviceOS': fake.random_element(elements=OSPLATFORM),
        'deviceType': fake.random_element(elements=('mobile', 'desktop')),
        'IPaddress' : fake.ipv4(),
        'playerAgeDemographics' : fake.random_element(elements=PLAYERAGE),
        'place' : fake.location_on_land()
    } for userId in range(config['General']['maxUsers'])]

    while True:

        tNow = int(time.time())
        
        hourOfDayGM = time.gmtime(tNow)[3]
        anomalyOn = hourOfDayGM < 17 or hourOfDayGM > 21 # anomaly means less revenue
        
        eventId = str(fake.random_int(min=0, max=9))
        sessionId = fake.random_int(min=0, max=config['General']['maxUsers']-1)
        userId = int(sessionId) // 10
        userRec = users[int(userId)]
        gameId = fake.random_element(elements=GAMEID)
        adId = fake.numerify('A-####')

        place = fake.location_on_land()
        ev = {
            'eventType': EVENTTYPE[int(eventId)],
            'eventTimestamp' : tNow - fake.random_int(min=1, max=100),
            'gameInfo' : gameId,
            'userId' : str(userId),
            'sessionId' : str(sessionId),
            'sessionStatus' : fake.random_element(elements=SESSIONSTATUS[anomalyOn]),
            'score' : fake.random_int(min=0, max=100000),
            'gameLevel' : str(fake.random_int(min=1, max=100)),
            'deviceType' : userRec['deviceType'],
            'deviceOS' : userRec['deviceOS'],
            'IPaddress' : userRec['IPaddress'],
            'adName' : adId,
            'eventRevenue': round(random.gauss(REVENUEPARAM[anomalyOn]['mu'], REVENUEPARAM[anomalyOn]['sigma']), 2),
            'playerAgeDemographics': userRec['playerAgeDemographics'],
            'adResponse' : fake.random_element(elements=ADRESPONSE),
            'latitude' : userRec['place'][0],
            'longitude' : userRec['place'][1],
            'place_name' : userRec['place'][2],
            'country_code' : userRec['place'][3],
            'timezone' : userRec['place'][4]
        }
        emitEvent(producer, eventTopic, ev)

        waitSecs = random.uniform(minSleep, maxSleep)
        logging.debug(f'wait time: {waitSecs}')
        time.sleep(waitSecs)

if __name__ == "__main__":
    main()

