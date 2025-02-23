from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import pika
import json
from datetime import datetime
import switch


class LoadBalancedController(switch.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(LoadBalancedController, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.metrics = {}
        self.switch_data =[]
        self.datapath_metadata = {}
        self.flow_threshold = 30  # Example flow count threshold
        self.controller_id = "3"  # Default ID
        self.setup_messaging()
        self.monitor_thread = hub.spawn(self._monitor)
        

    def setup_messaging(self):
        """Set up RabbitMQ connections for communication."""
        try:
            self.rabbitmq_host = 'localhost'
            self.rabbitmq_queue = 'controller'
            # Establish the connection to RabbitMQ
            self.connection = pika.BlockingConnection(pika.ConnectionParameters(self.rabbitmq_host))
            self.channel = self.connection.channel()
            # Declare the queue if it does not exist
            self.channel.queue_declare(queue=self.rabbitmq_queue, durable=True)
            self.logger.info("RabbitMQ connection established and queue declared.")
        except pika.exceptions.AMQPConnectionError as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.connection = None
            self.channel = None

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        """Track datapaths as they connect and disconnect."""
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if datapath.id not in self.datapaths:
                self.logger.debug('Register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('Unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]
                self.datapath_metadata.pop(datapath.id, None)

    def _monitor(self):
        """Periodically collect metrics and send to RabbitMQ."""
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            
            self.calculate_final_metrics()
            self.send_metrics_to_broker()
            hub.sleep(30)

    def _request_stats(self, datapath):
        """Request flow stats from a switch."""
        self.logger.debug('Send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

        # Track the time when the request was sent
        self.datapath_metadata[datapath.id] = {
            'last_request_time': datetime.now()
        }

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """Handle flow stats replies and send them to RabbitMQ."""
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
        
        # self.send_metrics_to_broker(metrics)
    
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
                return None  # Latency cannot be calculated yet

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

            
