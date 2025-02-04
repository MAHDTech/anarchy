#!/usr/bin/env python3

import base64
import flask
import gevent.pywsgi
import json
import logging
import os
import random
import re
import requests
import socket
import sys
import string
import threading
import time
import yaml

from copy import deepcopy
from datetime import datetime, timedelta

api = flask.Flask('rest')
callbacks = {}
domain = os.environ.get('ANARCHY_DOMAIN', 'anarchy.gpte.redhat.com')

callback_url = None
callback_token = None
simulate_job_result = None

def init():
    global logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(os.environ.get('LOGGING_LEVEL', 'DEBUG'))
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(threadName)s - %(message)s')
    handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.setLevel(os.environ.get('LOGGING_LEVEL', 'DEBUG'))
    logger.addHandler(handler)

def schedule_callback(after, event, job_id, msg, token, url):
    callbacks[(job_id,event)] = {
        "after": after,
        "token": token,
        "url": url,
        "data": {
            "event": event,
            "job_id": job_id,
            "msg": msg,
        }
    }

def callback_loop():
    while True:
        completed = []
        for key, callback in callbacks.copy().items():
            if time.time() < callback['after']:
                continue
            resp = requests.post(
                callback['url'],
                json=callback['data'],
                headers={ "Authorization": "Bearer " + callback['token'] },
                verify=False
            )
            logger.info(
                "%s - %s: %s",
                callback['url'],
                resp.status_code,
                resp.text
            )
            del callbacks[key]
        time.sleep(1)

@api.route('/api/v2/tokens/', methods=['POST'])
def api_v2_tokens_post():
    return flask.jsonify({
        "application": 1,
        "created": datetime.utcnow().isoformat() + 'Z',
        "expires": (datetime.utcnow() + timedelta(days=1)).isoformat() + 'Z',
        "id": 11111111,
        "token": "s3cr3tT0k3n"
    }), 201

@api.route('/api/v2/tokens/<string:token_id>/', methods=['DELETE'])
def api_v2_tokens_delete(token_id):
    return flask.jsonify({}), 204

@api.route('/api/v2/organizations/', methods=['GET'])
def api_v2_organizations_get():
    name = flask.request.args.get('name', 'default')
    return flask.jsonify({
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{
            "created": datetime.utcnow().isoformat() + 'Z',
            "id": 1,
            "description": name,
            "max_hosts": 0,
            "name": name,
            "type": "organization",
            "url": "/api/v2/organizations/1/",
        }]
    }), 200

@api.route('/api/v2/organizations/<string:org_id>/', methods=['PATCH'])
def api_v2_organizations_patch(org_id):
    return flask.jsonify({
        "created": datetime.utcnow().isoformat() + 'Z',
        "id": org_id,
        "description": "default",
        "max_hosts": 0,
        "name": "default",
        "type": "organization",
        "url": "/api/v2/organizations/1/",
    }), 200

@api.route('/api/v2/inventories/', methods=['GET'])
def api_v2_inventories_get():
    org_id = flask.request.args.get('organization')
    name = flask.request.args.get('name', 'default default')
    return flask.jsonify({
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{
            "created": datetime.utcnow().isoformat() + 'Z',
            "description": "",
            "host_filter": None,
            "id": 1,
            "kind": "",
            "name": name,
            "organization": org_id,
            "type": "inventory",
            "url": "/api/v2/inventories/1/",
        }]
    }), 200

@api.route('/api/v2/inventories/<string:inventory_id>/', methods=['PATCH'])
def api_v2_inventories_patch(inventory_id):
    return flask.jsonify({
        "created": datetime.utcnow().isoformat() + 'Z',
        "description": "",
        "host_filter": None,
        "id": inventory_id,
        "kind": "",
        "name": "default default",
        "organization": 1,
        "type": "inventory",
        "url": "/api/v2/inventories/1/",
    }), 200

@api.route('/api/v2/projects/', methods=['GET'])
def api_v2_projects_get():
    org_id = flask.request.args.get('organization')
    name = flask.request.args.get('name', 'default default')
    return flask.jsonify({
        "count": 1,
        "next": None,
        "previous": None,
        "results": [{
            "created": datetime.utcnow().isoformat() + 'Z',
            "custom_virtualenv": None,
            "id": 1,
            "name": name,
            "organization": org_id,
            "scm_branch": "development",
            "scm_clean": False,
            "scm_delete_on_update": False,
            "scm_refspec": "",
            "scm_type": "git",
            "scm_url": "https://github.com/redhat-cop/agnosticd.git",
            "scm_update_cache_timeout": 30,
            "scm_update_on_launch": True,
            "summary_fields": {},
            "timeout": 0,
            "type": "project",
            "url": "/api/v2/projects/1/",
        }]
    }), 200

@api.route('/api/v2/projects/<string:project_id>/', methods=['PATCH'])
def api_v2_projects_patch(project_id):
    ret = deepcopy(flask.request.json)
    ret['created']: datetime.utcnow().isoformat() + 'Z'
    ret['modified']: datetime.utcnow().isoformat() + 'Z'
    ret['id'] = project_id
    ret['summary_fields'] = dict()
    ret['url'] = '/api/v2/projects/{}/'.format(project_id)
    return flask.jsonify(ret), 200

@api.route('/api/v2/job_templates/', methods=['GET'])
def api_v2_job_templates_get():
    name = flask.request.args.get('name')
    results = []
    if name:
        results.append({
            "ask_inventory_on_launch": True,
            "id": 1,
            "name": name,
            "related": {
                "launch": "/api/v2/job_templates/1/launch/",
            },
            "type": "job_template",
            "url": "/api/v2/job_templates/1/",
        })
    return flask.jsonify({
        "count": len(results),
        "next": None,
        "previous": None,
        "results": results,
    }), 200

@api.route('/api/v2/job_templates/<string:job_template_id>/', methods=['PATCH'])
def api_v2_job_templates_patch(job_template_id):
    global callback_url, callback_token, simulate_job_result
    extra_vars = flask.request.json.get('extra_vars')
    if not extra_vars:
        flask.abort(400, description='extra_vars not passed')
    extra_vars = json.loads(extra_vars)
    simulate_job_result = extra_vars.get('simulate_job_result', 'successful')
    callback_token = extra_vars.get('agnosticd_callback_token')
    if not callback_token:
        flask.abort(400, description='agnosticd_callback_token not set in extra_vars')
    callback_url = extra_vars.get('agnosticd_callback_url')
    if not callback_url:
        flask.abort(400, description='agnosticd_callback_url not set in extra_vars')
    ret = deepcopy(flask.request.json)
    ret['created']: datetime.utcnow().isoformat() + 'Z'
    ret['id'] = job_template_id
    ret['modified'] = datetime.utcnow().isoformat() + 'Z'
    ret['type'] = 'job_template'
    ret['url'] = '/api/v2/job_templates/{}/'.format(job_template_id)
    logger.info("Callback URL %s", callback_url)
    return flask.jsonify(ret), 200

@api.route('/api/v2/job_templates/<string:job_template_id>/credentials/', methods=['GET'])
def api_v2_job_templates_credentials_get(job_template_id):
    return flask.jsonify({
        "count": 0,
        "next": None,
        "previous": None,
        "results": [],
    }), 200;

@api.route('/api/v2/job_templates/<string:job_template_id>/launch/', methods=['POST'])
def api_v2_job_templates_job_runner_launch_post(job_template_id):
    global callback_url, callback_token, simulate_job_result

    job_id = random.randint(1,10000000)
    if simulate_job_result == 'successful':
        schedule_callback(
            after=time.time() + 10,
            event='complete',
            job_id=job_id,
            msg='completed',
            token=callback_token,
            url=callback_url
        )
    return flask.jsonify({
        "id": job_id,
        "job": job_id,
        "status": '',
    }), 201

def job_data(job_id):
    data = {
        "status": "running",
        "related": {
            "cancel": "/api/v2/jobs/{}/cancel/".format(job_id),
        },
        "type": "job_template",
        "url": "/api/v2/jobs/{}/".format(job_id),
    }
    if simulate_job_result == 'successful':
        data['status'] = 'successful'
    else:
        data['status'] = simulate_job_result
    return data

@api.route('/api/v2/jobs/', methods=['GET'])
def api_v2_jobs_get():
    job_id = flask.request.args.get('id')
    if job_id:
        return flask.jsonify({
            "count": 1,
            "next": None,
            "previous": None,
            "results": [ job_data(job_id) ]
        }), 200
    else:
        return flask.jsonify({
            "count": 0,
            "next": None,
            "previous": None,
            "results": []
        }), 200

@api.route('/api/v2/jobs/<string:job_id>/', methods=['GET'])
def api_v2_jobs_id_get(job_id):
    return flask.jsonify(job_data(job_id))

@api.route('/api/v2/jobs/<string:job_id>/cancel/', methods=['GET'])
def api_v2_jobs_cancel_get(job_id):
    return flask.jsonify({
        "can_cancel": True
    }), 200

@api.route('/api/v2/jobs/<string:job_id>/cancel/', methods=['POST'])
def api_v2_jobs_cancel_post(job_id):
    return flask.jsonify({}), 202

@api.route('/runner/<string:runner_queue_name>/<string:runner_name>', methods=['GET', 'POST'])
def runner_get(runner_queue_name, runner_name):
    if flask.request.method == 'POST':
        logger.info("RUNNER POST %s %s %s", runner_queue_name, runner_name, flask.request.json)
        return flask.jsonify(None)

    logger.info("RUNNER GET")
    n = random.randint(0,2)
    if n == 0:
        return flask.jsonify(None)
    else:
        if n == 1:
            tasks = []
        else:
            tasks = [{
                'name': 'test failure',
                'fail': {
                    'msg': 'test failure'
                }
            }]
        return flask.jsonify({
            'apiVersion': domain + '/v1',
            'kind': 'AnarchyRun',
            'metadata': {
                'name': 'test'
            },
            'spec': {
                # vars? tasks?
                'action': {
                    'metadata': {
                        'name': 'test-action'
                    }
                },
                'event': {
                    'name': 'test',
                    'data': {
                    },
                    'tasks': tasks
                },
                'governor': {
                    'metadata': {
                        'name': 'test-governor'
                    }
                },
                'subject': {
                    'metadata': {
                        'name': 'test-subject'
                    }
                }
            }
        })

def main():
    """Main function."""

    init()
    logger.info("Starting test server")

    threading.Thread(
        name = 'callback',
        target = callback_loop
    ).start()

    http_server  = gevent.pywsgi.WSGIServer(('', 5000), api)
    http_server.serve_forever()

if __name__ == '__main__':
    main()
