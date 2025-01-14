from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.lib import hub
import pika  # RabbitMQ or other broker

import switch
from datetime import datetime
import joblib
import pandas as pd
from sklearn import svm
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix
from sklearn.metrics import accuracy_score

class SimpleMonitor13(switch.SimpleSwitch13):

    def __init__(self, *args, **kwargs):
        super(SimpleMonitor13, self).__init__(*args, **kwargs)
        self.datapaths = {}
        self.monitor_thread = hub.spawn(self._monitor)
        self.flow_threshold = 100  # Example flow count threshold for load balancing
        self.load_model()
        self.setup_messaging()

    def setup_messaging(self):
        # Set up the message broker (RabbitMQ in this case)
        self.connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue='controller_states')

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
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
        while True:
            for dp in self.datapaths.values():
                self._request_stats(dp)
            hub.sleep(10)  # Monitoring interval of 10 seconds

    def load_model(self):
        try:
            self.flow_model = joblib.load('best_svm_model.joblib')
            self.logger.info('Model loaded successfully')
        except OSError:
            self.logger.info("No pretrained model found, training a new one")
            self.flow_training()

    def _request_stats(self, datapath):
        self.logger.debug('Send stats request: %016x', datapath.id)
        parser = datapath.ofproto_parser
        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        datapath_id = ev.msg.datapath.id
        body = ev.msg.body
        flow_count = len(body)  # Count the number of flows for this switch
        self.logger.info(f"Switch {datapath_id}: {flow_count} active flows")

        # Send stats to message broker
        self.send_stats_to_broker(datapath_id, flow_count)

        # Check if the flow count exceeds the threshold and trigger load balancing
        if flow_count > self.flow_threshold:
            self.logger.warning(f"Switch {datapath_id} exceeds flow threshold ({self.flow_threshold}). Load balancing required!")
            self.trigger_load_balancing(datapath_id, flow_count)

    def send_stats_to_broker(self, datapath_id, flow_count):
        # Prepare state message to send to the broker
        state = {
            "controller_id": f"ryu{datapath_id}",
            "flow_count": flow_count,
            "timestamp": datetime.now().isoformat()
        }
        self.channel.basic_publish(exchange='',
                                   routing_key='controller_states',
                                   body=str(state))
        self.logger.info(f"Sent stats for datapath {datapath_id} to message broker.")

    def trigger_load_balancing(self, datapath_id, flow_count):
        # Implement load balancing logic here
        self.logger.info(f"Triggering load balancing for switch {datapath_id} with {flow_count} flows.")
        # Example: You could redistribute flows or migrate controllers

    def flow_training(self):
        self.logger.info("Flow Training ...")

        flow_dataset = pd.read_csv('FlowStatsfile.csv')
        flow_dataset.iloc[:, 2] = flow_dataset.iloc[:, 2].str.replace('.', '')
        flow_dataset.iloc[:, 3] = flow_dataset.iloc[:, 3].str.replace('.', '')
        flow_dataset.iloc[:, 5] = flow_dataset.iloc[:, 5].str.replace('.', '')

        X_flow = flow_dataset.iloc[:, :-1].values
        X_flow = X_flow.astype('float64')

        y_flow = flow_dataset.iloc[:, -1].values

        X_flow_train, X_flow_test, y_flow_train, y_flow_test = train_test_split(X_flow, y_flow, test_size=0.25, random_state=0)

        classifier = RandomForestClassifier(n_estimators=10, criterion="entropy", random_state=0)
        self.flow_model = classifier.fit(X_flow_train, y_flow_train)

        y_flow_pred = self.flow_model.predict(X_flow_test)

        self.logger.info("------------------------------------------------------------------------------")
        self.logger.info("Confusion matrix")
        cm = confusion_matrix(y_flow_test, y_flow_pred)
        self.logger.info(cm)

        acc = accuracy_score(y_flow_test, y_flow_pred)

        self.logger.info("Success accuracy = {0:.2f} %".format(acc * 100))
        fail = 1.0 - acc
        self.logger.info("Fail accuracy = {0:.2f} %".format(fail * 100))
        self.logger.info("------------------------------------------------------------------------------")
