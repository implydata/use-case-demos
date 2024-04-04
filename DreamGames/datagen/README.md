# Gaming data simulator

A data simulator that populates a number of Kafka topics with fake game analytics data.

## Invocation

```
python3 ./datagen.py -f ./datagen_config.yml [-d|-q] [-n]
```

Command options:

```
-n  Do not write to Kafka - send data to the console instead in human readable form
-q  Quiet mode, lowers the log level
-d  Debug mode, generate debug output
```

## Configuration

The main configuration is in `datagen_config.yml`. Usually you would configure the topics here; for unsecured Kafka also enter the bootstrap server in the Kafka settings.

Kafka settings are standard producer properties.

`datagen_config.yml` includes a file `datagen_secret.yml`, if it exists. This file can be used to store credentials for secure Kafka. DO NOT check that file into Github. A template is provided in this repository.

## Limitations

- Currently, satellite table records are emitted for every event. These will eventually be held in a state database.
- The `gameDetail` and `advertiserDetail` tables are dummies.
