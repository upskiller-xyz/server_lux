from __future__ import annotations
from flask import make_response, Request
from http import HTTPStatus

def get_request_input(request: Request, default=""):
    # print("external IP:", requests.get("https://ident.me").content)
    
    if request.method=="OPTIONS":
        return "", HTTPStatus.NO_CONTENT.value
    key="content"
    request_json = request.get_json()
    

    if request.args and key in request.args:
        return request.args.get(key), HTTPStatus.OK.value
    elif request_json and key in request_json:
        return request_json[key], HTTPStatus.OK.value
    else:
        print("params not defined, defaulting to {}".format(default))

        return default, HTTPStatus.NO_CONTENT.value