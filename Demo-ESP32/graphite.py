'''
class for communication with Graphite
'''
import socket
import time

class Graphite():
    '''
    Graphite Client
    '''
    hostname = ""
    port = 0

    def __init__(self, hostname, port):
        '''
        Set hostname and port
        '''
        self.hostname = hostname
        self.port = port

    def send_data(self, data, timestamp=False):
        '''
        Send data to plaintext input
        '''
        if time.time() < 692284226:
            raise Exception('Time not set!')
        if not timestamp:
            timestamp = time.time() + 946684800
        g_sock = socket.socket()
        try:
            g_sock.connect((self.hostname, self.port))
            g_msg = ""
            for key, val in data.items():
                g_msg += key+' '+str(val)+' '+str(timestamp)+'\n'
            g_sock.sendall(g_msg)
            g_sock.close()
        except Exception as graphite_error:
            print("Error in graphite", graphite_error)
            return "err"
        return True
