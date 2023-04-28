"""
Copyright (c) 2022 Cisco and/or its affiliates.
This software is licensed to you under the terms of the Cisco Sample
Code License, Version 1.1 (the "License"). You may obtain a copy of the
License at
               https://developer.cisco.com/docs/licenses
All use of the material herein must be in accordance with the terms of
the License. All rights not expressly granted by the License are
reserved. Unless required by applicable law or agreed to separately in
writing, software distributed under the License is distributed on an "AS
IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
or implied.
"""
import json
import os
import requests
import logging
import logging.config
import logging.handlers
from dotenv import load_dotenv
from datetime import datetime

from flask import Flask, render_template, jsonify, request
import hashlib
import base64
import hmac

# Load env variables
load_dotenv()

from logging.config import dictConfig

dictConfig({
    'version': 1,
    'formatters': {'default': {
        'format': '[%(asctime)s] %(levelname)s in %(module)s: %(message)s',
    }},
    'handlers': {'wsgi': {
        'class': 'logging.StreamHandler',
        'stream': 'ext://flask.logging.wsgi_errors_stream',
        'formatter': 'default'
    }},
    'root': {
        'level': 'INFO',
        'handlers': ['wsgi']
    }
})

# Flask initialization
app = Flask(__name__)
# app.secret_key = os.getenv('FLASK_SECRET_KEY')

@app.context_processor
def custom_context():
    options={}
    options["FEISHU_BOT_WEBHOOK_URL"]=os.getenv('FEISHU_BOT_WEBHOOK_URL')
    return options

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/notify',methods=['GET','POST'])
def receive_notification():
    json_data=request.get_json()
    app.logger.debug(f'Recieved Notification Data: {json_data}')

    # Map Message and Forward
    payload=map_message(json_data)
    response=forward_message_as_json(payload)

    reply_object=response
    return jsonify(reply_object)

def map_message(payload):
    # https: // open.larksuite.com / document / uAjLw4CM / ukTMukTMukTM / bot - v3 / use - custom - bots - in -a - group

    message=json.loads(render_template(f'messages/card.json',message=payload))

    if os.getenv('MESSAGE_SIGNATURE_VERIFICATION').lower()=='true':
        current_timestamp=datetime.now().timestamp()/1000
        msg_secret=os.getenv('MESSAGE_SIGNATURE_SECRET')
        if not msg_secret:
            app.logger.error('Unable to find Message Secret for Signature verification')
        else:
            message["timestamp"]= current_timestamp
            message["sign"]= gen_sign(current_timestamp,msg_secret)
            app.logger.info('Added Signature to Message')

    app.logger.debug(f'converted Message: {message}')

    return message


def gen_sign(timestamp, secret):
    # Concatenate timestamp and secret
    string_to_sign = '{}\n{}'.format(timestamp, secret)
    hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()

    # Encode the result with Base64
    sign = base64.b64encode(hmac_code).decode('utf-8')

    return sign

def forward_message_as_json(payload):
    # please refer event management documentation for more info
    # https://docs.servicenow.com/en-US/bundle/tokyo-it-operations-management/page/product/event-management/task/send-events-via-web-service.html
    url = f'{os.getenv("FEISHU_BOT_WEBHOOK_URL")}'
    headers = {
        'Accept': "application/json",
        'Content-Type': "application/json",
    }
    app.logger.debug(f'url: {url}, payload: {payload}')


    try:
        response= requests.post(url=url,headers=headers, json=payload)
        app.logger.info(f'Forwarded a message to Webhook URL {url}')
        app.logger.debug(f'Lark Response: {response.json()}')
        response=response.json()
    except Exception as err:
        app.logger.error(f'error forwarding message {err.msg}')

    return response


def enable_custom_logging():
    log_path = os.getenv('LOG_PATH') if os.getenv('LOG_PATH') else "logs"
    if not os.path.exists(log_path):
        os.mkdir(log_path)

    # Standard Log File Formatting
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Timed Rotating Log File Handler, rolls over to new log at midnight
    rotating_log_handler = logging.handlers.TimedRotatingFileHandler(filename=os.path.join(log_path, 'app.log'),when='midnight', backupCount=30)
    rotating_log_handler.setFormatter(file_formatter)

    # Registering to application logger
    app.logger.addHandler(rotating_log_handler)

if __name__ == "__main__":
    enable_custom_logging()
    if os.getenv('HTTPS_ENABLED').lower() == "true":
        app.run(host='0.0.0.0',ssl_context=(os.getenv("CERT_PATH"), os.getenv("KEY_PATH")))
    else:
        app.run(host='0.0.0.0')