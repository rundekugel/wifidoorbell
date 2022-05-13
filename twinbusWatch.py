#!/usr/bin/env python3
"""ritto door bell test"""

import sys
import socket
import machine
import time
import network 
import uos as os

__version__ = "0.5.1"
__author__  = "gaul1@lifesim.de"

up = 1
if up:
  from umqtt.robust import MQTTClient as mqtt
  portnam = 0
else:
  import paho.mqtt.client as mqtt
  portnam = None #"com7"
  machine.UART.port = portnam

emptybuf = b""
relpinnum = 2
ledpinnum = 2


class globs:
  sock = None
  sockL = None
  client = None
  verbosity = 4
  server="s3"
  port=1883
  #topic="comu/"
  topicpre = "comu/"
  doit = 1
  oben = b"testO"
  unten = b"testU"
  relais = b"testR"
  uartnum = 0
  uart = None
  uartbuf = emptybuf
  uartbufmax = 1024
  uartbaud = 31250
  sockport = 8888
  p13override = False


def on_connect(client, userdata, flags, rc):
  if globs.verbosity:
    print("Connected with result code " + str(rc))
  if up:
    pass
  else:
    client.subscribe(globs.topicpre+"cmd")
    client.publish(globs.topicpre + "stat", "connected")


def on_message(p1, p2, msg=None): #this is from std, not micro-python
  if up:
    topic,payload=p1,p2
  else:
    topic,payload = msg.topic, msg.payload
  if isinstance( payload, bytes):
      payload = payload.decode()
  if isinstance( topic, bytes):
      topic = topic.decode()
  if globs.verbosity>1:
    print(topic + " " + str(payload))
  if topic == "comu/cmd":
    if globs.verbosity == 1:
      print(topic + " " + str(payload))
    if "exit!" == payload:
      globs.doit=0
    m1,m2 = payload.split(':',1)  ,""
    if len(m1)>1: m1,m2 =m1
    if m1=="setu": globs.unten = m2
    if m1=="seto": globs.oben = m2
    if m1=="relais!": relais(1); time.sleep(1); relais(0);

def doSock(txmsg=b""):
  gl = globs.sockL
  if not globs.sockL:
    a=None
    try:
      a,ip = globs.sock.accept()
    except Exception as e:
      if e != 0 and globs.verbosity>3:
        print(str(e))
    if a:
      globs.sockL = a
      if globs.verbosity:
        globs.client.publish(globs.topicpre+"info", "sock conn."+str(ip))
  if globs.sockL:
    try:
      if txmsg:
        globs.sockL.send(txmsg)
      else:
        r=globs.sockL.send(globs.uartbuf)
        globs.uartbuf = globs.uartbuf[r:]
        if globs.verbosity>3:
          print(r)
    except:
      globs.sockL.close()
      globs.sockL=0
      if globs.verbosity >1:
        print("sock closed.")
        globs.client.publish(globs.topicpre+"info", "sock closed.")

  if gl:
    try:
      rx = globs.sockL.recv(99)
    except:
      rx=None
    if rx is not None:
      if globs.verbosity>3:
        print(rx)
      if b"exit!" in rx:
        globs.doit = 0
      elif b"relais!" in rx:
        relais(1); time.sleep(1); relais(0);
      elif rx[:2]==b"u:":
        globs.uartbuf += rx[2:].decode()
      elif rx[:2]==b"v=":
        globs.verbosity = int(rx[2])
      elif rx[:2]==b"??":
        globs.sockL.send(b"ack:"+rx)
      elif rx[:2]==b"m:":
        globs.client.publish(globs.topicpre+"info", rx[2:])
      elif rx==b"":
        globs.sockL.close()
        globs.sockL=0
        if globs.verbosity >1:
          print("sock closed.")
          globs.client.publish(globs.topicpre+"info", "sock closed.")
        
  #todo: check if connection still active

def led(onoff):
  machine.Pin(ledpinnum, machine.Pin.OUT).value( not onoff) # led is inverse

def relais(onoff):
  machine.Pin(relpinnum, machine.Pin.OUT).value(onoff) # 

def reattach():
  uart = machine.UART(0, 115200)
  os.dupterm(uart, 1)
  
def detach():
  os.dupterm(None, 1)  
  
def tryWlan(timeout=5):  
  while 1:
    ip = network.WLAN(network.STA_IF).ifconfig()[0]
    if ip != "0.0.0.0": return timeout
    time.sleep(1)
    led(timeout &1)
    timeout-=1
    if timeout <1: return 0
  
def main():
  led(1)
  if globs.verbosity>1: print("python V:"+sys.version)
  
  if up:
    if not tryWlan(): return
    if not globs.p13override and (machine.Pin(13, machine.Pin.IN).value() == 0): return
    if globs.uartnum is not None:
      if globs.uartnum==0:  detach()
      globs.uart= machine.UART(globs.uartnum, baudrate=globs.uartbaud, timeout=1)
  else:
    globs.uart = machine.UART(port=portnam, baudrate=globs.uartbaud, timeout=1)
    
    
  led(0)
  globs.sock = socket.socket()
  globs.sock.bind(("", globs.sockport))  #only ip allowed
  globs.sock.listen(1)
  globs.sock.setblocking(0)
  globs.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  led(1)
  globs.client = mqtt(client_id="tw",server="s3")
  client = globs.client
  client.on_connect = on_connect
  client.on_message = on_message
  server, port = globs.server, globs.port
  if ":" in server:
    sp = server.split(":")
    server,port = sp
  if not up:
    client.will_set(globs.topicpre + "stat", "break")
    client.connect()
    client.loop_start()
  else:
    client.set_last_will(globs.topicpre + "stat", "break")
    client.set_callback(on_message)
    client.connect()
    client.subscribe(globs.topicpre+"cmd")
    d={"connected":1,"ip":network.WLAN(network.STA_IF).ifconfig()[0]}
    client.publish(globs.topicpre + "stat", str(d))
  
  globs.pr = machine.Pin(relpinnum, machine.Pin.OUT); globs.pr.value(0)

  bufwasempty=1
  while globs.doit:
    led(1)
    timeout=100
    while 1:
      if globs.uart:
        try:
          rx = globs.uart.read()
        except:
          rx=""
      else: rx=""
      if not rx: break
      globs.uartbuf += rx
      if len(rx) > globs.uartbufmax:
        rx = rx[205:]
      timeout-=1
      if timeout<1: break
    if rx and bufwasempty:
      client.publish(globs.topicpre + "rx", "newData")
      bufwasempty = 0

    if globs.oben in globs.uartbuf:
      client.publish(globs.topicpre+"rx","oben")
      globs.uartbuf=emptybuf
    elif globs.unten in globs.uartbuf:
      client.publish(globs.topicpre+"rx","unten")
      globs.uartbuf = emptybuf
    elif globs.relais in globs.uartbuf:
      client.publish(globs.topicpre + "rx", "relais")
      globs.uartbuf = emptybuf
      globs.pr.on() ; time.sleep(1); globs.pr.off()

    if not globs.uartbuf:
      bufwasempty=1
    doSock()
    led(0)
    time.sleep(.2)
    if up:
      client.check_msg()
    else:
      client.loop()
  #end
  globs.uart.close()
  led(0)
  if globs.sockL:
    globs.sockL.close()
  reattach()
  globs.sock.close()
  print("done.")

if __name__ == "__main__":
  main()
  reattach()
  
#eof
