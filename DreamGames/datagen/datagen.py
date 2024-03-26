import yaml
import json
import random
import math
from scipy import interpolate
import time
import argparse, sys, logging
import socket
import signal
from faker import Faker
from confluent_kafka import Producer
from mergedeep import merge

fake = Faker()

msgCount = 0

def emit(producer, topic, key, emitRecord):
    global msgCount
    # sid = emitRecord['sid']
    if producer is None:
        print(f'{key}|{json.dumps(emitRecord)}')
    else:
        producer.produce(topic, key=str(key), value=str(emitRecord))
        msgCount += 1
        if msgCount >= 2000:
            producer.flush()
            msgCount = 0
        producer.poll(0)

def emitEvent(p, t, emitRecord):
    emit(p, t, emitRecord["event_key"], emitRecord)


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
        eventTopic = None
    else:
        eventTopic = config['General']['eventTopic']
        logging.debug(f'eventTopic: {eventTopic}')

        kafkaconf = config['Kafka']
        kafkaconf['client.id'] = socket.gethostname()
        logging.debug(f'Kafka client configuration: {kafkaconf}')
        producer = Producer(kafkaconf)

    minSleep = config['General']['minSleep']
    if minSleep is None:
        minSleep = 0.01
    maxSleep = config['General']['maxSleep']
    if maxSleep is None:
        maxSleep = 0.04

    while True:

        # TODO generate record

        ev = {
            'timestamp' : int(time.time()),
            'event_key' : '1111',
            'eventdata' : 'dummy'
        }
        emitEvent(producer, eventTopic, ev)

        waitSecs = random.uniform(minSleep, maxSleep)
        logging.debug(f'wait time: {waitSecs}')
        time.sleep(waitSecs)

if __name__ == "__main__":
    main()

