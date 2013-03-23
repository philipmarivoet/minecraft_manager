import subprocess
import socket
import signal
import sys
import threading
import time
import re
import cmd
import os

#running = True

#def signal_handler(signal, frame):
#  global running
#  print 'You pressed Ctrl+C!'
#  running = False

#signal.signal(signal.SIGINT, signal_handler)

class MinecraftServerMonitor(threading.Thread):

  def __init__(self, server):
    self.server = server

    threading.Thread.__init__(self)

  def start(self):
    self.running = True
    threading.Thread.start(self)

  def stop(self):
    self.running = False
    threading.Thread.join(self, 10)
    
  def run(self):
    #... [INFO] There are 0/20 players online:
    online_pattern = re.compile('.*There are (\d+)/\d* players.*')
                                
    while self.running:
      line = self.server.readline()
      if line is None or line == '':
        break
      
      line = line.strip()
      print line

      # analyze line
      match = online_pattern.match(line)
      if match:
        player_count = int(match.group(1))
        self.server.set_player_count(player_count)
  
class MinecraftServer(threading.Thread):

  def __init__(self):
    # read server.properties to get the port number
    f = open('server.properties', 'r')
    properties = f.readlines()
    for prop in properties:
      prop = prop.strip()
      if prop.startswith('#') or len(prop) == 0:
        continue
      field, value = prop.split('=')
      if field == 'server-port':
        port = int(value)

    print "SERVER PORT: ", port
    self.port = port

    self.player_count = 0
    self.listen_socket = None
    self.server = None

    threading.Thread.__init__(self)

  def start(self):
    self.running = True
    threading.Thread.start(self)

  def stop(self):
    self.running = False
    if self.listen_socket:
      print "Close socket"
      self.listen_socket.shutdown(socket.SHUT_RDWR)
      self.listen_socket.close()
      
    threading.Thread.join(self, 10)
    
  def run(self):
    while self.running:
      # start up server proxy listener

      print "=" * 60
      print "SERVER MONITOR"
      print "Waiting for players ..."
      print "=" * 60
      
      self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
      self.listen_socket.bind(('', self.port))

      # wait for knock on door
      self.listen_socket.listen(1)
      conn, addr = self.listen_socket.accept()

      conn.close()
      self.listen_socket.close()
      self.listen_socket = None
      
      if not self.running:
        break
      
      # start the real server
      print "=" * 60
      print "SERVER MONITOR"
      print "Starting minecraft server ..."
      print "=" * 60

      if os.path.exists('minecraft_launcher.jar'):
        cmd = "java -Xms512M -Xmx1024M -jar minecraft_launcher.jar nogui"
      else:
        cmd = "java -Xms512M -Xmx1024M -jar minecraft_server.jar nogui"
      self.server = subprocess.Popen(cmd.split(), stderr = subprocess.PIPE, stdin = subprocess.PIPE);

      monitor = MinecraftServerMonitor(self)
      monitor.start()

      #
      # monitor server status
      #

      expire_init = 10
      
      expire = expire_init
      
      while self.running:
        time.sleep(60)

        self.execute('list')
        time.sleep(5)
        
        if self.player_count == 0:
          expire -= 1
        else:
          expire = expire_init
          
        if expire == 0:
          break

      print "=" * 60
      print "SERVER MONITOR"
      print "Stopping minecraft server ..."
      print "=" * 60

      self.execute('stop')

      result = None
      for _ in range(10):
        print "Checking minecraft server exit code ..."
        result = self.server.poll()
        if not result is None:
          print "Server exited ok ..."
          break
        time.sleep(10)

      if result is None:
        print "Terminating minecraft server ..."
        self.server.terminate()
        
      monitor.stop()
      self.server = None
      
  def set_player_count(self, count):
    self.player_count = count
    
  def readline(self):
    return self.server.stderr.readline()
  
  def execute(self, command):
    if self.server:
      self.server.stdin.write(command + '\n')


class MinecraftConsole(cmd.Cmd):

  def __init__(self, server):
    self.server = server
    self.prompt = ">>"
    cmd.Cmd.__init__(self)

  def run(self):
      while True:
          try:
              self.cmdloop()
          except KeyboardInterrupt:
              print("^C")
              return

  def do_exit(self, line):
    return True

  def default(self, line):
    try:
      self.server.execute(line)
    except:
      return True
    
ms = MinecraftServer()
ms.start()

console = MinecraftConsole(ms)
console.run()

print "STOPPING MINECRAFT SERVER"

ms.stop()
