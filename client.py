#!.venv/bin/python3

debug = False #disables RFID reading for testing on non-pi devices.
disable_delay = .7 #Number of secconds of inactivity before the device sends the "Pause" signal.
action_auth_key = "fd452c9c-6382-4cbe-842c-4e03edc83e08" #This should be retreived from https://landoncloud.win.
target_domain = "https://api.landoncloud.win" #The domain of the server this code will connect to: "https://example.com"

import json
import base64
import time
import threading
import logging
from os import path, mkdir, getcwd

import rsa
import requests
if debug == False:
    print("Imported")
    import RPi.GPIO as GPIO
    from mfrc522 import SimpleMFRC522
    rfidReader = reader = SimpleMFRC522()

event_trigger = threading.Event()

logging_path = path.join(getcwd(), "logs")
print(f"Logs located at: {logging_path}")
if not path.exists(logging_path):
    mkdir(logging_path)
logging.basicConfig(level=logging.DEBUG, filename=f"{logging_path}/TT_Client.log", filemode="w")


with open("public.pem", "r") as f:
    public_key = rsa.PublicKey.load_pkcs1(f.read())

start_time = 999999999999999
disabled = False


def main():
    global start_time
    global disabled

    last_read_id = 0

    time.sleep(1)
    print("Init complete. Starting read process.")
    logging.info("Init complete. Starting read process.")
    while True:

        start_time = time.time()
        
        if debug == True:
            input("Press Enter to trigger timer.\n")
            
            id = 987654321
            
            print(id)
            disabled = True
            trigger_action(id, "start")
            disabled = False

        else:
            logging.debug("Reading...")
            
            id = rfidReader.read()[0]

            logging.debug(f"Read: {id}")

            if not id == last_read_id or disabled == True:
                last_read_id = id

                disabled = True
                trigger_action(id=id, action="start")
                disabled = False

        if disabled == True:
            start_time = 999999999999999
            disabled = False

def clock():
    global start_time
    global disabled

    while True:
        if not disabled:
            duration = time.time() - start_time

            if duration >= disable_delay:
                logging.debug("Stop time has been reached.")
                trigger_action(id=0, action="stop")
                start_time = 0
                disabled = True
        
        time.sleep(.3)

def trigger_action(id, action):
    logging.info(f"API Action Trigger - id: {id} - action: {action}")

    logging.debug("Preping OTK (one-time-key) request.")
    headers = {
        "Content-Type":"application/json"
    }

    otk_url = target_domain + "/otk"

    otk_data = {
        "action_auth_key": encrypt_message(action_auth_key)
    }

    try:
        logging.debug("Sending one-time-key request.")
        response = requests.get(url=otk_url, data=json.dumps(otk_data), headers=headers)
        json_result = json.loads(response.content)
        if json_result["status"] == "ok":
            otk = json_result["otk"]
        else:
            print("Error while retreving one time key.")
            exit()
    
    except requests.exceptions.ConnectionError:
        logging.warning("Connection to server failed. Unable to get OTK.")
        return "Error"
    except Exception as error:

        try:
            logging.warning(f"Exception while retreiving OTK: {error}")
            logging.debug(f"Response from failed request: {response}")
        except:
            logging.debug("An addional error occured while processing error from OTK. This probably means there was an error with the connection.")

        return "Error"

    logging.debug("Preping action request.")
    data = {
        "action_auth_key": encrypt_message(action_auth_key),
        "otk": encrypt_message(otk),
        "action": encrypt_message(action),
        "card_id": encrypt_message(str(id)),
    }

    status_result = ""

    action_url = target_domain + "/action"

    try:
        logging.debug("Sending action request.")
        response = requests.post(url=action_url, data=json.dumps(data), headers=headers)
        json_result = json.loads(response.content)
        status_result = json_result["status"]
        status_error = json_result["error"]
        logging.debug(f"Action request response - status: {json_result['status']} - error: {status_error}")

    except requests.exceptions.ConnectionError:
        logging.warning("Connection to server failed. Unable to send action.")
        return "Error"
    
    except Exception as error:                                                                              
        try:
            logging.warning(f"Exception while sending action: {error}")
            logging.debug(f"Response from failed request: {response}")
        except:
            logging.debug("An addional error occured while processing error from action request. This probably means there was an error with the connection.")
    
    return status_result

def encrypt_message(text):
    cipher = rsa.encrypt(text.encode(), public_key)
    base_64_text = base64.b64encode(cipher).decode()
    return base_64_text


if __name__ == "__main__":
    print()
    for try_count in range(3):
        if trigger_action(id=0, action="verify_auth") == "valid" or debug == True:
            logging.info("Authentication Verified")
            break
        logging.warning("Unable to connect to server. Retrying in 5 secconds...")
        time.sleep(5)
    else:
        logging.critical("Unable to connect to server. Authentication verification failed.")
        exit()
    
    thread_main = threading.Thread(target=main, daemon=False)
    thread_clock = threading.Thread(target=clock, daemon=True)
    
    logging.info("Starting core threads.")
    thread_main.start()
    thread_clock.start()