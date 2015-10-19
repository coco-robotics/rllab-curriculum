import zmq
import pickle
import cloudpickle
from optparse import OptionParser
from misc.console import mkdir_p
import numpy as np

def launch_sampler(gen_sampler):
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    parser = OptionParser()
    parser.add_option("-p", "--port", dest="port",
                      help="Port to bind the socket on")
    (options, args) = parser.parse_args()
    socket.connect("tcp://localhost:%s" % options.port)
    socket.send('ack')
    message = socket.recv()
    socket.send('ack')
    with gen_sampler(message) as sampler:
        while True:
            message = pickle.loads(socket.recv())
            itr = message[0]
            tot_rewards, n_traj, all_obs, Q_est, all_pi_old, all_actions, all_states = \
                sampler.collect_samples(*message)
            to_send = (tot_rewards, n_traj, all_obs, Q_est, all_pi_old, all_actions)
            while True:
                try:
                    print "sending data..."
                    socket.send(cloudpickle.dumps(to_send))
                    break
                except MemoryError:
                    print 'Memory error. Retrying...'
                    next
