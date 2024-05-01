# Observabiility using Imply, Prometheus and Kafka


To demo the Observability use case, the idea began with having some metrics in Prometheus, send them to Kafka and monitor them in Imply. What better way than to use metrics from my own Imply Hybrid cluster for this demo :) 

Please refer to Part 1a if you want to emit Druid metrics from Imply cluster to Prometheus --OR-- Part 1b if you want to emit K8s metrics to Prometheus. And refer to part 2 if you have some metrics already available in Prometheus and would like to send them to Kafka so they can be analysed in Imply/Druid.

[Part 1a: Emit Druid metrics from Imply cluster to Prometheus](#part-1a-emit-druid-metrics-from-imply-cluster-to-prometheus)

[Part 1b: Emit K8s metrics from EKS/K8s cluster to Prometheus](#part-1b-emit-k8s-metrics-from-eksk8s-cluster-to-prometheus)

[Part 2: Sending metrics from Prometheus to Kafka and analyse them in Imply](#part-2-sending-metrics-from-prometheus-to-kafka-and-analyse-them-in-imply)

Prometheus is an open-source monitoring and alerting tool designed for cloud-native environments. It collects and stores metrics as time-series data, offering robust monitoring capabilities.

### How Prometheus Works

Prometheus operates on a pull model, where it regularly scrapes metrics from configured endpoints. Key aspects of Prometheus include:

- **Data Collection**: Prometheus collects data in the form of time series.
- **Scraping**: The Prometheus server queries data sources, known as exporters, at defined intervals.
- **Storage**: Metrics are stored locally on disk, enabling fast data storage and querying.

## Part 1a: Emit Druid metrics from Imply cluster to Prometheus


## Prometheus-emitter Extension

The Prometheus-emitter extension configures an HTTP server within the Druid process, allowing Prometheus to scrape metrics.


### Integration Workflow

1. **Load the prometheus-emitter extension**: Load prometheus-emitter extension on Imply cluster you want to emit Druid metrics from. Use pull deps to download the community extension for Prometheus, upload it to S3 and add it as a custom extension in Imply Manager.
   
![image-20240307-165628](https://github.com/implydata/use-case-demos/assets/91908414/d98abf1b-82a7-416e-a29c-f59be971bf67)

2. **Prometheus Server**: Configure Prometheus to scrape metrics from Imply Nodes. Use different ports for colocated services to emit to Prometheus.

3. **Port Configuration**: Utilize different ports for colocated services to emit metrics to Prometheus.

![image-20240307-165351](https://github.com/implydata/use-case-demos/assets/91908414/e210a8e3-3224-4bcd-ac83-e6aa9057f05a)
![image-20240307-165424](https://github.com/implydata/use-case-demos/assets/91908414/e9ad760d-b1ff-4c30-85f1-39b5e20f2c41)

## Installation Guide

### Install Prometheus on EC2

Ensure that Prometheus is installed on an EC2 instance within the same VPC as the Imply Hybrid cluster to scrape metrics effectively.

1. **Download Prometheus**:
```
wget https://github.com/prometheus/prometheus/releases/download/v2.50.1/prometheus-2.50.1.linux-amd64.tar.gz
```

2. **Extract Files**:
```
tar -xvf prometheus-2.50.1.linux-amd64.tar.gz
```

3. **Navigate to Directory**:
```
cd prometheus
```

4. **Update Configuration**:
Update the `prometheus.yml` file with scrape configurations to target Druid metrics from the Imply Hybrid cluster.


5. **Create systemd Unit File**:
```
sudo vi /etc/systemd/system/prometheus.service
```

6. **Configure Service**:
Update the `prometheus.service` file with appropriate configurations.


7. **Reload systemd**:
```
sudo systemctl daemon-reload
```

8. **Start Prometheus Service**:
```
sudo systemctl start prometheus
```

9. **Enable Autostart**:
```
sudo systemctl enable prometheus
```

10. **Access Dashboard**: Prometheus dashboard should be accessible on port 9090.

![image-20240307-170308](https://github.com/implydata/use-case-demos/assets/91908414/678fecf8-9eb4-495f-a3f6-72bf78e4d6a1)


## Part 1b: Emit K8s metrics from EKS/K8s cluster to Prometheus

### Install Prometheus on the EKS cluster using Helm

1. **Create namespace for Prometheus**:
```
kubectl create namespace prometheus
```

2. **Add the prometheus-community chart repository**:
```
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
```

3. **Save default values**
```
helm show values prometheus-community/prometheus > prometheus.yaml
```

4. **Deploy Prometheus**:
```
helm upgrade -i prometheus prometheus-community/prometheus \
    --namespace prometheus \
    --set alertmanager.persistentVolume.storageClass="gp2" \
    --set server.persistentVolume.storageClass="gp2" \
    --set server.service.type=LoadBalancer
    --values prometheus.yaml
```

Since prometheus is deployed on the same EKS/K8s cluster, it should now start scraping K8s metrics from the nodes.


## Part 2: Sending metrics from Prometheus to Kafka and analyse them in Imply

### Install Prometheus-Kafka Adapter

Download tar file for Prometheus Kafka adapter (It would be easy if you install it on the same machine where Prometheus server is runnning)
```
wget https://github.com/Telefonica/prometheus-kafka-adapter/archive/refs/tags/1.9.0.tar.gz

tar -xvf 1.9.0.tar.gz

mv 1.9.0.tar.gz prometheus-kafka-adapter
```
Install docker and docker-compose

```
sudo yum update 
sudo yum install docker
sudo systemctl enable docker
sudo systemctl start docker

sudo curl -L https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m) -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
docker-compose version
```
Configure docker-compose.yml

```
services:
  prometheus-kafka-adapter:
    image: telefonica/prometheus-kafka-adapter:1.9.0
    environment:
      KAFKA_BROKER_LIST: pkc-4nym6.us-east-1.aws.confluent.cloud:9092
      KAFKA_TOPIC: imply-metrics
      SERIALIZATION_FORMAT: json
      PORT: 8080
      LOG_LEVEL: debug
      GIN_MODE: release
      KAFKA_SECURITY_PROTOCOL: SASL_SSL
      KAFKA_SASL_MECHANISM: PLAIN
      KAFKA_SASL_USERNAME: "<<redacted>>"
      KAFKA_SASL_PASSWORD: "<<redacted>>"
    ports:
      - "8080:8080"
```

Run Prometheus Kafka adapter container

```
docker-compose up -d
```

### Update prometheus.yml

In order for Prometheus to send metrics to the Prometheus Kafka adapter, you need to configure Prometheus to use the adapter as a remote write endpoint in its configuration (prometheus.yml). 

If the adapter is running on the same machine as Prometheus server, update prometheus.yml with the below remote_write url:

```
remote_write:
   - url: "http://localhost:8080/receive"
```

If the adapter is running outside the K8s cluster, update prometheus.yaml with the remote_write url having ip of machine where it is running:

```
remoteWrite:
   - url: "http://10.102.3.152:8080/receive"
```

Restart Prometheus if it is set to run as a systemd service

```
sudo systemctl restart prometheus
```

OR Upgrade the helm release using the new version of prometheus.yaml
```
helm upgrade prometheus prometheus-community/prometheus \
    --namespace prometheus \
    --set alertmanager.persistentVolume.storageClass="gp2" \
    --set server.persistentVolume.storageClass="gp2" \
    --set server.service.type=LoadBalancer
    --values prometheus.yaml
```

You should now see metrics flowing from Prometheus to Kafka

<img width="1452" alt="image-20240325-014119" src="https://github.com/implydata/use-case-demos/assets/91908414/34213ae2-ec4f-441f-98dc-acdd7742036f">

### Ingest Kafka topic to Imply Polaris

It's super easy to ingest data from Apache Kafka or Conlfuent Cloud. Druid was purpose built to ingest data from Kafka and has native Kafka integration. Imply Polaris, a fully managed service (or Druid-as-a-Service as we like to call it), offers an easy way to create a connection, point Imply to your Kafka topic and start ingestion of your data from Kafka to Imply. Doc link: https://docs.imply.io/polaris/ingest-from-confluent-cloud/

<img width="1786" alt="Screenshot 2024-04-09 at 15 46 28" src="https://github.com/implydata/use-case-demos/assets/91908414/d25b9b9c-79df-4b42-acdf-71f8a9013a8c">

### Analyse the Observabilility metrics in Imply Polaris

Once the data starts getting ingested into Imply Polaris, you can build visualisations and dashboards to analyse your observability metrics. Key thing to note here is you will now be able to analyse both real-time and historical data of Observability metrics in one place.

<img width="1792" alt="Screenshot 2024-04-09 at 15 56 38" src="https://github.com/implydata/use-case-demos/assets/91908414/006b9d52-9474-4b7b-af91-4b41377d8923">


## Conclusion

By following this guide, you can effectively set up Prometheus to monitor Druid metrics coming from Imply/Druid cluster, or send Prometheus metrics to Kafka and analyse them in Imply - an easy way to ensure comprehensive monitoring and alerting capabilities for your cloud-native environment.
