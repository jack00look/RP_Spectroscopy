import zerorpc
import time

class HelloRPC(object):
    def hello(self, name):
        return "Hello, %s" % name

    @zerorpc.stream
    def subscribe_to_signals(self):
        """Yields a signal every 2 seconds."""
        count = 0
        while count < 5: # Limit for prototype safety
            time.sleep(2)
            count += 1
            yield f"SIGNAL_{count}"

s = zerorpc.Server(HelloRPC())
s.bind("tcp://0.0.0.0:4242")
s.run()
