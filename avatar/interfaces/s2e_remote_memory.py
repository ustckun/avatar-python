import threading
import logging
import sys
import json
import socket
import time
from select import select

log = logging.getLogger("avatar.remote_memory_interface")

class RemoteMemoryInterface(object):
    def __init__(self):
        self._read_handler = None
        self._write_handler = None
        
    def set_read_handler(self, listener):
        self._read_handler = listener
        
    def set_write_handler(self, listener):
        self._write_handler = listener
        
    def _handle_read(self, params):
        assert(self._read_handler) #Read handler must be installed when this is called

        params["value"] = self._read_handler(params)
            
        return params["value"]
            
    def _handle_write(self, params):
        assert(self._write_handler) #Write handler must be installed when this is called

        self._write_handler(params)

class S2ERemoteMemoryInterface(RemoteMemoryInterface):
        def __init__(self, sock_address):
            super(S2ERemoteMemoryInterface, self).__init__()
            self._thread = threading.Thread(target = self._run)

            self._sock_address = sock_address
            self._stop = threading.Event()
            
        def start(self):
            self._thread.start()

        def _run(self):
            
            retries=1
            while retries < 10:
                try:
                    log.debug("Connecting to S2E RemoteMemory plugin at %s:%d", self._sock_address[0], self._sock_address[1])
                    sock = socket.create_connection(self._sock_address)
                    log.info("Connection to RemoteMemory plugin established")
                    retries=10
                except Exception:
                    log.exception("Connection to S2E RemoteMemory plugin failed (%d tries)" % retries)
                    time.sleep(3)
                    retries = retries+1
                    sock=None
            
            #TODO: Do proper error signalling
            if not sock:
                sys.exit(1)
            
            while not self._stop.is_set():
                buffer = ""
                while True:
                    if self._stop.is_set():
                        return
                    (rd, _, _) = select([sock], [], [], 1)
                    if rd:
                        buffer += sock.recv(1).decode(encoding = 'ascii')
                        try:
                            # this is outrageous
                            request = json.loads(buffer)
                            log.debug('buf: %s' % repr(buffer))
                            buffer = "" # reset the buffer if we were able to parse it
                            request["cmd"] # wait for cmd?
                            break
                        except:
                            # wait for more data
                            pass
                try:
                    if request["cmd"] == "read":
                        params = {"address" : int(request["params"]["address"], 16),
                                  "size": int(request["params"]["size"], 16),
                                  "cpu_state": request["cpu_state"]}
                        value = self._handle_read(params)
                        json_string = json.dumps({"reply": "read", "value": "0x%x" % value}) + "\n"
                        sock.send(json_string.encode(encoding = 'ascii'))
                    elif request["cmd"] == "write":
                        params = {"address" : int(request["params"]["address"], 16),
                                  "size": int(request["params"]["size"], 16),
                                  "value": int(request["params"]["value"], 16),
                                  "cpu_state": request["cpu_state"]}
                        self._handle_write(params)
                except Exception:
                    log.exception("Error in remote memory interface")
                    
        def stop(self):
            self._stop.set()
    
