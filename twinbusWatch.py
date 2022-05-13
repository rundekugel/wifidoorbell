#!/bin/usr/env python3

"""ritto door bell test"""

import socket
import machine
import time
import network 

up = 1
if up:
  from umqtt.robust import MQTTClient as mqtt
  portnam = 0
else:
  import paho.mqtt.client as mqtt
  portnam = "com7"
  machine.UART.port = portnam

emptybuf = b""
pinnum = 2
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
  uartnum = None
  uart = None
  uartbuf = emptybuf
  uartbufmax = 1024
  sockport = 8888


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
      if globs.verbosity>3:
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
        # globs.uartbuf = emptybuf
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
        
  #todo: check if connection still active

def led(onoff):
  machine.Pin(ledpinnum, machine.Pin.OUT, not onoff); # led is inverse

def relais(onoff):
  machine.Pin(pinnum, machine.Pin.OUT, onoff); # 

def main():
  if up:
    if globs.uartnum is not None:
      globs.uart= machine.UART(globs.uartnum, baudrate=32000, timeout=1)
  else:
    globs.uart = machine.UART(port=portnam, baudrate=32000, timeout=1)

  globs.sock = socket.socket()
  globs.sock.bind(("127.0.0.1", globs.sockport))  #only ip allowed
  globs.sock.listen(1)
  globs.sock.setblocking(0)
  globs.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

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
  
  if globs.uart:  
    globs.uartbuf = globs.uart.read()

  globs.pr = machine.Pin(pinnum, machine.Pin.OUT, 0);

  bufwasempty=1
  while globs.doit:
    while 1:
      if globs.uart:
        rx = globs.uart.read()
      else: rx=""
      if not rx: break
      globs.uartbuf += rx
      if len(rx) > globs.uartbufmax:
        rx = rx[65:]
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
    time.sleep(.2)
    if up:
      client.check_msg()
    else:
      client.loop()
  #end
  if globs.sockL:
    globs.sockL.close()
  globs.sock.close()
  print("done.")

if __name__ == "__main__":
  main()

#eof
