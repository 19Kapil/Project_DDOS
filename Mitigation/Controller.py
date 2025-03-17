from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub

import pika
import json
import switchm
from datetime import datetime
from xgboost import XGBClassifier
import pandas as pd


class SimpleMonitor13(switchm.SimpleSwitch13):

    def __init__(self, *args, **kwargs):

        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.metrics = {}
        self.ddos = 0
        self.switch_data =[]
        self.datapath_metadata = {}
        self.flow_threshold = 30  # Example flow count threshold
        self.controller_id = "1"  # Default ID
        self.load_model()
        self.setup_messaging()
        self.monitor_thread = hub.spawn(self._monitor)

    def setup_messaging(self):
        """Set up RabbitMQ connections for communication."""
        try:
            self.rabbitmq_host = 'localhost'
            self.rabbitmq_queue = 'controller'
            # Establish the connection to RabbitMQ
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(host = self.rabbitmq_host,heartbeat=600))
            self.channel = self.connection.channel()
            # Declare the queue if it does not exist
            self.channel.queue_declare(queue=self.rabbitmq_queue, durable=True)
            self.logger.info("RabbitMQ connection established and queue declared.")
        except pika.exceptions.AMQPConnectionError as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.reconnect_rabbitmq() 

    def reconnect_rabbitmq(self):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host = self.rabbitmq_host,heartbeat=600))
        self.channel = self.connection.channel()


    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def _monitor(self):
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)

            self.calculate_final_metrics()
            if self.ddos == 0:
                self.send_metrics_to_broker()

            self.flow_predict()
            hub.sleep(10)

            
    
    def load_model(self):
        try:
            self.flow_model = XGBClassifier()
            self.flow_model.load_model("xgb_best_model (3).json")
        except OSError:
            self.logger.info("No pretrained model found ,training a new one")
            self.flow_training()

    def _request_stats(self, datapath):
        self.logger.debug('send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        # Track the time when the request was sent
        self.datapath_metadata[datapath.id] = {
            'last_request_time': datetime.now()
        }

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):

        timestamp = datetime.now()
        timestamp = timestamp.timestamp()

        datapath_id = ev.msg.datapath.id
        body = ev.msg.body
        flow_count = len(body)  # Count the number of flows for this switch
        self.logger.info(f"Switch {datapath_id}: {flow_count} active flows")
        # Calculate latency
        # latency = self.calculate_latency()
        metrics = {
                "switch_id": datapath_id,
                "latency": self.calculate_latency(datapath_id),
                "load": flow_count,
                "timestamp": datetime.now().isoformat()
            }
        self.switch_data.append(metrics)

        file0 = open("PredictFlowStatsfile.csv","w")
        file0.write('timestamp,datapath_id,flow_id,ip_src,tp_src,ip_dst,tp_dst,ip_proto,icmp_code,icmp_type,flow_duration_sec,flow_duration_nsec,idle_timeout,hard_timeout,flags,packet_count,byte_count,packet_count_per_second,packet_count_per_nsecond,byte_count_per_second,byte_count_per_nsecond\n')
        icmp_code = -1
        icmp_type = -1
        tp_src = 0
        tp_dst = 0

        for stat in sorted([flow for flow in body if (flow.priority == 1) ], key=lambda flow:
            (flow.match['eth_type'],flow.match['ipv4_src'],flow.match['ipv4_dst'],flow.match['ip_proto'])):
        
            ip_src = stat.match['ipv4_src']
            ip_dst = stat.match['ipv4_dst']
            ip_proto = stat.match['ip_proto']
            
            if stat.match['ip_proto'] == 1:
                icmp_code = stat.match['icmpv4_code']
                icmp_type = stat.match['icmpv4_type']
                
            elif stat.match['ip_proto'] == 6:
                tp_src = stat.match['tcp_src']
                tp_dst = stat.match['tcp_dst']

            elif stat.match['ip_proto'] == 17:
                tp_src = stat.match['udp_src']
                tp_dst = stat.match['udp_dst']

            flow_id = str(ip_src) + str(tp_src) + str(ip_dst) + str(tp_dst) + str(ip_proto)
          
            try:
                packet_count_per_second = stat.packet_count/stat.duration_sec
                packet_count_per_nsecond = stat.packet_count/stat.duration_nsec
            except:
                packet_count_per_second = 0
                packet_count_per_nsecond = 0
                
            try:
                byte_count_per_second = stat.byte_count/stat.duration_sec
                byte_count_per_nsecond = stat.byte_count/stat.duration_nsec
            except:
                byte_count_per_second = 0
                byte_count_per_nsecond = 0
                
            file0.write("{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{},{}\n"
                .format(timestamp, ev.msg.datapath.id, flow_id, ip_src, tp_src,ip_dst, tp_dst,
                        stat.match['ip_proto'],icmp_code,icmp_type,
                        stat.duration_sec, stat.duration_nsec,
                        stat.idle_timeout, stat.hard_timeout,
                        stat.flags, stat.packet_count,stat.byte_count,
                        packet_count_per_second,packet_count_per_nsecond,
                        byte_count_per_second,byte_count_per_nsecond))
            
        file0.close()

    def calculate_final_metrics(self):
        total_latency = 0
        total_load = 0
        switch_count = len(self.switch_data)

        for metrics in self.switch_data:
            
            total_latency += metrics["latency"]
            
            total_load += metrics["load"]

        avg_latency = total_latency / switch_count if switch_count > 0 else 0

        self.metrics = {
            "controller_id": self.controller_id,
            "total_switches": switch_count,
            "latency": avg_latency,
            "load": total_load,
            "connected_switches": list(self.datapaths.keys()),
            "timestamp": datetime.now().isoformat()
        }

    def calculate_latency(self, datapath_id):
        """Calculate latency dynamically based on timestamps."""
        try:
            # Example: Use datapath's flow stats and track request/response times
            metadata = self.datapath_metadata.get(datapath_id, {})
            start_time = metadata.get('last_request_time', None)
            if not start_time:
                return 0  # Latency cannot be calculated yet

            current_time = datetime.now()
            latency = (current_time - start_time).total_seconds() * 1000  # Convert to milliseconds
            return latency
        except Exception as e:
            self.logger.error(f"Error calculating latency for {datapath_id}: {e}")
            return None


    def calculate_load(self):
        """Calculate load based on the number of datapaths."""
        return len(self.datapaths)  # Number of connected switches

    def send_metrics_to_broker(self):
        """Publish metrics to RabbitMQ."""
        if not self.channel and self.connection or self.connection.is_closed:
            self.logger.error("RabbitMQ connection is not available. Cannot send metrics.")
            return

        self.channel.basic_publish(
            exchange='',
            routing_key=self.rabbitmq_queue,
            body=json.dumps(self.metrics)
        )
        self.logger.info(f"Sent metrics: {self.metrics}")
        self.switch_data = []

    def close_messaging(self):
        if self.connection:
            self.connection.close()
            self.logger.info("RabbitMq closed")

    def flow_predict(self):
        try:
            predict_flow_dataset = pd.read_csv('PredictFlowStatsfile.csv')

            predict_flow_dataset.drop("timestamp",axis =1 , inplace=True)
            predict_flow_dataset.drop("tp_dst",axis =1 ,inplace=True)

            predict_flow_dataset.iloc[:, 1] = predict_flow_dataset.iloc[:, 1].str.replace('.', '')
            predict_flow_dataset.iloc[:, 2] = predict_flow_dataset.iloc[:, 2].str.replace('.', '')
            predict_flow_dataset.iloc[:, 4] = predict_flow_dataset.iloc[:, 4].str.replace('.', '')
            
            X_flow = predict_flow_dataset
            X_flow = X_flow.astype('float64')
            y_flow_pred = self.flow_model.predict(X_flow)
            
            legitimate_trafic = 0
            ddos_trafic = 0

            for i in y_flow_pred:
                if i == 0:
                    legitimate_trafic = legitimate_trafic + 1
                else:
                    ddos_trafic = ddos_trafic + 1
                    victim = int(predict_flow_dataset.iloc[i, 4])%20
                    
                    
                    

            self.logger.info("------------------------------------------------------------------------------")
            if (legitimate_trafic/len(y_flow_pred)*100) > 80:
                self.ddos = 0
                self.logger.info("Traffic is Legitimate!")
            else:
                self.logger.info("NOTICE!! DoS Attack in Progress!!!")
                self.logger.info("Victim Host: h{}".format(victim))
                print("Mitigation process in progress!")
                self.ddos = 1
                self.mitigation = 1

            self.logger.info("------------------------------------------------------------------------------")
            
            file0 = open("PredictFlowStatsfile.csv","w")
            
            file0.write('timestamp,datapath_id,flow_id,ip_src,tp_src,ip_dst,tp_dst,ip_proto,icmp_code,icmp_type,flow_duration_sec,flow_duration_nsec,idle_timeout,hard_timeout,flags,packet_count,byte_count,packet_count_per_second,packet_count_per_nsecond,byte_count_per_second,byte_count_per_nsecond\n')
            file0.close()

        except:
            pass