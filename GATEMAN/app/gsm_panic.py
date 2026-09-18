"""
gsm_panic.py
------------
Turns a $3 SIM800L GSM module into an offline panic-alert receiver.

How it works:
  Anyone (resident, guard, passerby) sends an SMS containing a trigger
  word (e.g. "HELP") to the SIM card plugged into this module. No app,
  no internet, no data plan needed on their end — just basic SMS,
  which works on any phone anywhere there's GSM signal.

  This code polls the module every few seconds using AT commands
  (the standard language GSM modems speak), and any matching message
  fires the on_alert callback with the sender's number and message.

This runs in a background thread so it doesn't block the FastAPI app.
"""

import re
import time
import threading

try:
    import serial
except ImportError:
    serial = None  # allows the rest of the app to run even if pyserial
                    # isn't installed yet / no GSM hardware is connected


class GSMPanicListener:
    def __init__(self, port: str, baudrate: int = 9600,
                 trigger_keywords=("HELP", "PANIC", "SOS"), on_alert=None):
        self.port = port
        self.baudrate = baudrate
        self.trigger_keywords = [k.upper() for k in trigger_keywords]
        self.on_alert = on_alert
        self._stop = False
        self.ser = None

    def _send_at(self, command: str, wait: float = 1.0) -> str:
        self.ser.write((command + "\r\n").encode())
        time.sleep(wait)
        return self.ser.read(self.ser.in_waiting or 1).decode(errors="ignore")

    def start(self):
        if serial is None:
            print("[GATEMAN GSM] pyserial not installed — panic-alert listener disabled. "
                  "Run: pip install pyserial")
            return
        try:
            self.ser = serial.Serial(self.port, self.baudrate, timeout=1)
        except Exception as e:
            print(f"[GATEMAN GSM] Couldn't open {self.port}: {e}. "
                  "Panic-alert listener disabled — check the COM port and wiring.")
            return

        time.sleep(2)  # give the module time to settle after opening the port
        self._send_at("AT")            # basic "are you there" check
        self._send_at("AT+CMGF=1")     # text mode (not the harder-to-parse PDU mode)

        print(f"[GATEMAN GSM] Panic-alert listener active on {self.port}.")
        thread = threading.Thread(target=self._poll_loop, daemon=True)
        thread.start()

    def _poll_loop(self):
        while not self._stop:
            try:
                response = self._send_at('AT+CMGL="REC UNREAD"', wait=2.0)
                self._process_messages(response)
            except Exception as e:
                print(f"[GATEMAN GSM] Error polling modem: {e}")
            time.sleep(5)

    def _process_messages(self, response: str):
        # A matching line looks like:
        #   +CMGL: 1,"REC UNREAD","+2348012345678",,"26/09/14,10:00:00+04"
        # with the actual SMS text on the following line.
        pattern = re.compile(r'\+CMGL:\s*(\d+),"REC UNREAD","([^"]+)"')
        lines = response.split("\r\n")

        for i, line in enumerate(lines):
            match = pattern.search(line)
            if not match:
                continue
            index, sender = match.groups()
            message_text = lines[i + 1].strip() if i + 1 < len(lines) else ""

            if any(keyword in message_text.upper() for keyword in self.trigger_keywords):
                if self.on_alert:
                    self.on_alert(sender, message_text)

            # Delete the message after reading it so we don't re-process
            # it on the next poll (the SIM has very limited storage).
            self._send_at(f"AT+CMGD={index}")

    def stop(self):
        self._stop = True
        if self.ser:
            self.ser.close()
