from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import pika  # RabbitMQ library
import json
from datetime import datetime
import switch


class LoadBalancedController(switch.SimpleSwitch13):
    def __init__(self, *args, **kwargs):
        super(LoadBalancedController, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.migration_thread = hub.spawn(self._consume_migration_commands)
        self.flow_threshold = 30  # Example flow count threshold
        self.setup_messaging()

    def setup_messaging(self):
        """Set up RabbitMQ connections for communication."""
        try:
            # Producer connection to send stats
            self.producer_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            self.producer_channel = self.producer_connection.channel()
            self.producer_channel.queue_declare(queue='controller_states')

            # Consumer connection to receive migration commands
            self.consumer_connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
            self.consumer_channel = self.consumer_connection.channel()
            self.consumer_channel.queue_declare(queue='migration_commands')
        except pika.exceptions.AMQPConnectionError as e:
            self.logger.error(f"Failed to connect to RabbitMQ: {e}")
            self.producer_connection = None
            self.consumer_connection = None

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

    def _monitor(self):
        """Periodically request stats from switches."""
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)  # Monitoring interval

    def _request_stats(self, datapath):
        """Request flow stats from a switch."""
        self.logger.debug('Send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """Handle flow stats replies and send them to RabbitMQ."""
        datapath_id = ev.msg.datapath.id
        body = ev.msg.body
        flow_count = len(body)  # Count the number of flows for this switch

        self.logger.info(f"Switch {datapath_id}: {flow_count} active flows")
        if flow_count > self.flow_threshold:
        # Send stats to the message broker
            self.send_stats_to_broker(datapath_id, flow_count)
            self._consume_migration_commands()
            self.handle_migration_command()

    def send_stats_to_broker(self, datapath_id, flow_count):
        """Publish controller stats to RabbitMQ."""
        if not self.producer_connection or self.producer_connection.is_closed:
            self.logger.error("RabbitMQ producer connection is not available. Cannot send stats.")
            return

        state = {
            "controller_id": f"1",
            "flow_count": flow_count,
            "timestamp": datetime.now().isoformat()
        }

        self.producer_channel.basic_publish(
            exchange='',
            routing_key='controller_states',
            body=json.dumps(state)
        )
        self.logger.info(f"Sent stats for datapath {datapath_id} to RabbitMQ.")

    def _consume_migration_commands(self):
        """Consume migration commands from RabbitMQ."""
        if not self.consumer_connection or self.consumer_connection.is_closed:
            self.logger.error("RabbitMQ consumer connection is not available.")
            return

        def callback(ch, method, properties, body):
            try:
                migration_command = json.loads(body.decode('utf-8'))
                self.logger.info(f"Received migration command: {migration_command}")
                self.handle_migration_command(migration_command)
            except json.JSONDecodeError as e:
                self.logger.error(f"Failed to decode migration command: {e}")

        self.consumer_channel.basic_consume(
            queue='migration_commands',
            on_message_callback=callback,
            auto_ack=True
        )

        self.logger.info("Started consuming migration commands.")
        self.consumer_channel.start_consuming()

    def handle_migration_command(self, migration_command):
        """Handle received migration commands."""
        from_controller = migration_command["from"]
        to_controller = migration_command["to"]
        switch_id = migration_command["switch_id"]

        if from_controller == f"ryu{self.dpid}":
            # Logic to migrate the switch to another controller
            self.logger.info(f"Initiating migration of {switch_id} to {to_controller}.")
            # Migration logic would involve modifying flow rules or reassigning ownership
        else:
            self.logger.info(f"Migration command not for this controller (target: {to_controller}).")
