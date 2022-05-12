#!/bin/usr/env python3

"""ritto door bell test"""

import socket
import machine
import time

up=0
if up:
  from umqttsimple import MQTTClient as mqtt
  portnam = 0
else:
  import paho.mqtt.client as mqtt
  portnam = "com7"
  machine.UART.port = portnam

emptybuf = b""
pinnum = 2

class globs:
  sock = None
  sockL = None
  client = None
  verbosity = 3
  server="s3"
  port=1883
  #topic="comu/"
  topicpre = "comu/"
  doit = 1
  oben = b"testO"
  unten = b"testU"
  relais = b"testR"
  uart0 = None
  uartbuf = emptybuf
  uartbufmax = 1024


def onRx():
  if globs.verbosity:
    print("rx:")
    #print(uart0.rx)


def on_connect(client, userdata, flags, rc):
  if globs.verbosity:
    print("Connected with result code " + str(rc))
  client.subscribe(globs.topicpre+"cmd")
  client.publish(globs.topicpre + "stat", "connected")


def on_message(client, userdata, msg):
  if isinstance( msg.payload, bytes):
      msg.payload = msg.payload.decode()
  if globs.verbosity>1:
    print(msg.topic + " " + str(msg.payload))
  if msg.topic == "comu/cmd":
    if globs.verbosity == 1:
      print(msg.topic + " " + str(msg.payload))
    if "exit!" == msg.payload:
      globs.doit=0
    m1,m2 = msg.payload.split(':',1)  ,""
    if len(m1)>1: m1,m2 =m1
    if m1=="setu": globs.unten = m2
    if m1=="seto": globs.oben = m2

def doSock(txmsg=b""):
  gl = globs.sockL
  if not globs.sockL:
    a=None
    try:
      a,ip = globs.sock.accept()
    except:
      pass
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
      if globs.verbosity>4:
        print(rx)
      if b"exit!" in rx:
        globs.doit = 0
  #todo: check if connection still active



def main():
  globs.uart0 = machine.UART(port=portnam, baudrate=115200, timeout=1)

  globs.sock = socket.socket()
  globs.sock.bind(("localhost", 8888))
  globs.sock.listen()
  globs.sock.setblocking(0)

  globs.client = mqtt.Client()
  client = globs.client
  client.on_connect = on_connect
  client.on_message = on_message
  server, port = globs.server, globs.port
  if ":" in server:
    sp = server.split(":")
    server,port = sp
  client.will_set(globs.topicpre + "stat", "break")
  client.connect(server, port, 60)
  client.loop_start()
  globs.uartbuf = globs.uart0.read()

  globs.pr = machine.Pin(pinnum, machine.Pin.OUT, 0);

  bufwasempty=1
  while globs.doit:
    while 1:
      rx = globs.uart0.read()
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
    client.loop()

  globs.sock.close()
  print("done.")

if __name__ == "__main__":
  main()

#eof
